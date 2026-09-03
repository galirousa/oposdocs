"""Harvest behaviour: idempotence, throttling, dedupe and failure containment.

Every test mocks the network. The point of the ledger is that a second pass
over the same day costs one HTTP request, and that is asserted by counting
calls, not by inspection.
"""

import datetime as dt
import json
from pathlib import Path
from unittest import mock

import pytest

from documents.models import Document
from oposiciones.factories import OposicionFactory
from sources import boe, tasks
from sources.factories import HarvestedItemFactory, HarvestRuleFactory
from sources.models import HarvestedItem, HarvestRun

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "boe_sumario_20260901.json"
DAY = dt.date(2026, 9, 1)


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text())


@pytest.fixture(autouse=True)
def _no_pipeline():
    """The ingestion pipeline has its own tests; keep these about harvesting."""
    with mock.patch("documents.ingest.start_pipeline") as started:
        yield started


@pytest.fixture(autouse=True)
def _no_delay(settings):
    settings.HARVEST_DOWNLOAD_DELAY = 0


@pytest.fixture(autouse=True)
def _clear_lock():
    tasks._release_lock()
    yield
    tasks._release_lock()


def _pdf(identificador: str) -> bytes:
    """Unique bytes per item, so SHA-256 dedupe behaves as it would in life."""
    return b"%PDF-1.4 " + identificador.encode()


class TestHarvestDay:
    def test_imports_every_item_as_pending_official(self, payload):
        with (
            mock.patch.object(boe, "fetch_summary", return_value=payload),
            mock.patch.object(boe, "download", side_effect=lambda url, **kw: _pdf(url)),
        ):
            run = tasks.harvest_day(DAY)

        assert run.status == HarvestRun.Status.OK
        assert run.items_seen == 4
        assert run.items_imported == 4
        documents = Document.objects.all()
        assert documents.count() == 4
        # The user approves before anything is public: official source, public
        # visibility, but still pending moderation.
        assert all(d.source_type == Document.SourceType.OFFICIAL for d in documents)
        assert all(d.moderation_status == Document.ModerationStatus.PENDING for d in documents)
        assert all(d.license == "official_public" for d in documents)
        assert not any(d.is_publicly_visible for d in documents)

    def test_description_is_written_so_pages_are_not_thin(self, payload):
        with (
            mock.patch.object(boe, "fetch_summary", return_value=payload),
            mock.patch.object(boe, "download", side_effect=lambda url, **kw: _pdf(url)),
        ):
            tasks.harvest_day(DAY)
        document = Document.objects.first()
        assert "Referencia: BOE-A-2026-" in document.description
        assert not document.is_thin

    def test_second_run_downloads_nothing(self, payload):
        with (
            mock.patch.object(boe, "fetch_summary", return_value=payload),
            mock.patch.object(boe, "download", side_effect=lambda url, **kw: _pdf(url)) as download,
        ):
            tasks.harvest_day(DAY)
            assert download.call_count == 4
            download.reset_mock()
            tasks.harvest_day(DAY)
            assert download.call_count == 0
        assert HarvestRun.objects.filter(fecha=DAY).count() == 1
        assert Document.objects.count() == 4
        # Counters describe the second attempt, not a replay of the first.
        run = HarvestRun.objects.get(fecha=DAY)
        assert run.items_seen == 4
        assert run.items_imported == 0
        assert run.items_duplicate == 0

    def test_no_edition_is_recorded_not_an_error(self):
        with mock.patch.object(boe, "fetch_summary", side_effect=boe.NoEditionError):
            run = tasks.harvest_day(dt.date(2026, 8, 30))
        assert run.status == HarvestRun.Status.NO_EDITION
        assert run.is_complete
        assert not Document.objects.exists()

    def test_upstream_failure_leaves_a_retryable_run(self):
        with mock.patch.object(boe, "fetch_summary", side_effect=boe.BoeUnavailableError("503")):
            run = tasks.harvest_day(DAY)
        assert run.status == HarvestRun.Status.FAILED
        assert not run.is_complete
        assert "503" in run.error

    def test_one_bad_download_does_not_lose_the_day(self, payload):
        calls = {"n": 0}

        def flaky(url, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise boe.BoeUnavailableError("timeout")
            return _pdf(url)

        with (
            mock.patch.object(boe, "fetch_summary", return_value=payload),
            mock.patch.object(boe, "download", side_effect=flaky),
        ):
            run = tasks.harvest_day(DAY)

        assert run.items_imported == 3
        assert run.items_failed == 1
        assert run.status == HarvestRun.Status.OK
        failed = HarvestedItem.objects.get(status=HarvestedItem.Status.FAILED)
        assert "timeout" in failed.error

    def test_identical_file_is_deduped_not_stored_twice(self, payload):
        with (
            mock.patch.object(boe, "fetch_summary", return_value=payload),
            mock.patch.object(boe, "download", return_value=b"%PDF-identical"),
        ):
            run = tasks.harvest_day(DAY)
        assert Document.objects.count() == 1
        assert run.items_imported == 1
        assert run.items_duplicate == 3

    def test_matched_oposicion_is_attached(self, payload):
        oposicion = OposicionFactory(nombre="Consejo General del Poder Judicial")
        HarvestRuleFactory(oposicion=oposicion, terminos="Escuela Judicial")
        with (
            mock.patch.object(boe, "fetch_summary", return_value=payload),
            mock.patch.object(boe, "download", side_effect=lambda url, **kw: _pdf(url)),
        ):
            tasks.harvest_day(DAY)
        matched = HarvestedItem.objects.exclude(matched_oposiciones=None)
        assert matched.exists()
        assert oposicion in matched.first().document.oposiciones.all()

    def test_item_without_pdf_is_ignored(self):
        item = HarvestedItemFactory(url_pdf="")
        assert tasks.import_item(item) == HarvestedItem.Status.IGNORED
        assert not Document.objects.exists()


class TestLocking:
    def test_recent_stands_down_when_a_harvest_is_running(self):
        assert tasks._acquire_lock()
        with mock.patch.object(tasks, "harvest_day") as harvest_day:
            assert tasks.harvest_recent() == "locked"
        harvest_day.assert_not_called()

    def test_lock_is_released_after_a_run(self):
        with mock.patch.object(tasks, "harvest_day"):
            tasks.harvest_recent(days=1)
        assert not tasks.harvest_is_running()

    def test_lock_is_released_even_when_a_day_explodes(self):
        with (
            mock.patch.object(tasks, "harvest_day", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            tasks.harvest_recent(days=1)
        assert not tasks.harvest_is_running()


class TestHarvestRecent:
    def test_walks_the_catchup_window_newest_first(self, settings):
        with mock.patch.object(tasks, "harvest_day") as harvest_day:
            tasks.harvest_recent(days=3)
        days = [call.args[0] for call in harvest_day.call_args_list]
        assert len(days) == 3
        assert days == sorted(days, reverse=True)

    def test_skips_days_already_completed(self):
        from sources.factories import HarvestRunFactory

        today = dt.date.today()
        HarvestRunFactory(fecha=today - dt.timedelta(days=1), status=HarvestRun.Status.OK)
        with mock.patch.object(tasks, "harvest_day") as harvest_day:
            tasks.harvest_recent(days=2)
        assert len(harvest_day.call_args_list) == 1

    def test_retries_a_previously_failed_day(self):
        from sources.factories import HarvestRunFactory

        target = dt.date.today() - dt.timedelta(days=1)
        HarvestRunFactory(fecha=target, status=HarvestRun.Status.FAILED)
        with mock.patch.object(tasks, "harvest_day") as harvest_day:
            tasks.harvest_recent(days=1)
        assert [call.args[0] for call in harvest_day.call_args_list] == [target]


class TestBackfill:
    def test_walks_backwards_one_day_per_tick(self, settings):
        settings.HARVEST_BACKFILL_COUNTDOWN = 7
        start = dt.date(2026, 8, 20)
        with (
            mock.patch.object(tasks, "harvest_day") as harvest_day,
            mock.patch.object(tasks.harvest_backfill, "apply_async") as enqueue,
        ):
            tasks.harvest_backfill(day="2026-08-22", stop=start.isoformat())

        harvest_day.assert_called_once()
        assert harvest_day.call_args.args[0] == dt.date(2026, 8, 22)
        # The next day is queued only after this one finished — that ordering
        # is the whole "one at a time" guarantee.
        kwargs = enqueue.call_args.kwargs
        assert kwargs["kwargs"]["day"] == "2026-08-21"
        assert kwargs["countdown"] == 7
        assert kwargs["queue"] == "harvest"

    def test_stops_at_the_start_date(self):
        with (
            mock.patch.object(tasks, "harvest_day") as harvest_day,
            mock.patch.object(tasks.harvest_backfill, "apply_async") as enqueue,
        ):
            result = tasks.harvest_backfill(day="2026-08-20", stop="2026-08-20")
        harvest_day.assert_called_once()
        enqueue.assert_not_called()
        assert "harvested" in result

    def test_does_not_run_past_the_start_date(self):
        with mock.patch.object(tasks, "harvest_day") as harvest_day:
            result = tasks.harvest_backfill(day="2026-08-19", stop="2026-08-20")
        harvest_day.assert_not_called()
        assert "complete" in result

    def test_reschedules_the_same_day_when_the_lock_is_held(self):
        assert tasks._acquire_lock()
        with (
            mock.patch.object(tasks, "harvest_day") as harvest_day,
            mock.patch.object(tasks.harvest_backfill, "apply_async") as enqueue,
        ):
            result = tasks.harvest_backfill(day="2026-08-22", stop="2026-08-20")
        harvest_day.assert_not_called()
        assert enqueue.call_args.kwargs["kwargs"]["day"] == "2026-08-22"
        assert "locked" in result

    def test_skips_a_day_already_completed(self):
        from sources.factories import HarvestRunFactory

        HarvestRunFactory(fecha=dt.date(2026, 8, 22), status=HarvestRun.Status.OK)
        with (
            mock.patch.object(tasks, "harvest_day") as harvest_day,
            mock.patch.object(tasks.harvest_backfill, "apply_async"),
        ):
            tasks.harvest_backfill(day="2026-08-22", stop="2026-08-20")
        harvest_day.assert_not_called()

    def test_default_start_comes_from_settings(self, settings):
        settings.HARVEST_BACKFILL_START = "2020-01-01"
        from sources.models import default_backfill_start

        assert default_backfill_start() == dt.date(2020, 1, 1)
