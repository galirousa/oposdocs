"""Harvest tasks, built to never overwhelm a single small server.

Four independent mechanisms keep the load flat, because any one of them alone
leaves a hole:

1. **A dedicated ``harvest`` queue with one worker at concurrency 1.** Two
   harvest tasks can never execute at the same time, whatever enqueues them.
2. **A Redis lock.** Beat firing while a multi-hour backfill is still running
   is a no-op rather than a task piling up behind it. Nothing queues up waiting.
3. **Sequential downloads inside a day**, with a delay between them, instead of
   fanning out one task per PDF. Bandwidth stays at one file at a time.
4. **A self-chaining backfill**: one day per tick, and the next day is only
   enqueued once the current one has finished. Six years of BOE therefore
   arrives as a slow trickle that can be stopped, resumed or waited out.

The heavy lifting downstream (pdftotext, OCR) already has its own capped queue,
so imported documents cannot starve the web workers either.
"""

import datetime as dt
import logging
import time

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from documents.ingest import store_document
from documents.models import Document

from . import boe
from .models import Boletin, HarvestedItem, HarvestRun, default_backfill_start

logger = logging.getLogger(__name__)

LOCK_KEY = "sources:harvest:lock"
LOCK_VALUE = "held"


def _acquire_lock() -> bool:
    """Atomic SETNX via the Redis cache backend."""
    return cache.add(LOCK_KEY, LOCK_VALUE, timeout=settings.HARVEST_LOCK_TIMEOUT)


def _release_lock() -> None:
    cache.delete(LOCK_KEY)


def harvest_is_running() -> bool:
    return cache.get(LOCK_KEY) == LOCK_VALUE


# --- One day, end to end ----------------------------------------------------


def harvest_day(day: dt.date, *, boletin: str = Boletin.BOE) -> HarvestRun:
    """Fetch one day's summary and import its documents, sequentially.

    Synchronous and lock-free by design: the callers (the Celery tasks and the
    management command) own the locking, so this function is also directly
    usable from a shell for debugging one bad day.
    """
    run, _ = HarvestRun.objects.update_or_create(
        boletin=boletin,
        fecha=day,
        defaults={
            "status": HarvestRun.Status.RUNNING,
            "error": "",
            "finished_at": None,
            # Counters describe THIS attempt. Without the reset, re-running a
            # day that is already imported re-saves the first run's totals and
            # reports work that did not happen.
            "items_seen": 0,
            "items_imported": 0,
            "items_duplicate": 0,
            "items_failed": 0,
        },
    )
    try:
        payload = boe.fetch_summary(day)
    except boe.NoEditionError:
        run.status = HarvestRun.Status.NO_EDITION
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
        logger.info("No BOE edition on %s", day)
        return run
    except boe.BoeUnavailableError as exc:
        run.status = HarvestRun.Status.FAILED
        run.error = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])
        logger.warning("BOE unavailable for %s: %s", day, exc)
        return run

    items = list(boe.iter_items(payload))
    run.items_seen = len(items)
    run.save(update_fields=["items_seen"])

    for index, parsed in enumerate(items):
        item = _upsert_item(parsed, boletin=boletin)
        if item.status != HarvestedItem.Status.NEW:
            continue  # already dealt with on an earlier run
        if index:
            # Politeness: one file at a time, paced. BOE is a public service.
            time.sleep(settings.HARVEST_DOWNLOAD_DELAY)
        outcome = import_item(item)
        if outcome == HarvestedItem.Status.IMPORTED:
            run.items_imported += 1
        elif outcome == HarvestedItem.Status.DUPLICATE:
            run.items_duplicate += 1
        elif outcome == HarvestedItem.Status.FAILED:
            run.items_failed += 1

    run.status = HarvestRun.Status.OK
    run.finished_at = timezone.now()
    run.save(
        update_fields=[
            "status",
            "items_imported",
            "items_duplicate",
            "items_failed",
            "finished_at",
        ]
    )
    logger.info(
        "Harvested %s %s: %s items, %s imported, %s duplicate, %s failed",
        boletin,
        day,
        run.items_seen,
        run.items_imported,
        run.items_duplicate,
        run.items_failed,
    )
    return run


def _upsert_item(parsed: boe.BoeItem, *, boletin: str) -> HarvestedItem:
    """Create the ledger row, or return the existing one untouched.

    BOE's ``identificador`` is the natural key, so a second pass over the same
    day recognises everything it already has and downloads nothing.
    """
    item, created = HarvestedItem.objects.get_or_create(
        identificador=parsed.identificador,
        defaults={
            "boletin": boletin,
            "fecha_publicacion": parsed.fecha_publicacion,
            "seccion": parsed.seccion,
            "departamento": parsed.departamento[:300],
            "epigrafe": parsed.epigrafe[:300],
            "titulo": parsed.titulo,
            "url_pdf": parsed.url_pdf,
            "url_html": parsed.url_html,
            "url_xml": parsed.url_xml,
            "size_bytes": parsed.size_bytes,
        },
    )
    if created:
        rules = item.matching_rules()
        if rules:
            item.matched_oposiciones.set([rule.oposicion for rule in rules])
    return item


def import_item(item: HarvestedItem) -> str:
    """Download one item's PDF and register it as an official Document.

    Imported documents land as ``PENDING``: official material is safe to host
    but an unreviewed flood of it would create thousands of thin public pages,
    which is exactly what the editorial queue is for.
    """
    if not item.url_pdf:
        item.status = HarvestedItem.Status.IGNORED
        item.error = "El item no publica PDF."
        item.save(update_fields=["status", "error", "updated_at"])
        return item.status

    try:
        blob = boe.download(item.url_pdf)
    except (boe.BoeUnavailableError, ValueError) as exc:
        item.status = HarvestedItem.Status.FAILED
        item.error = str(exc)
        item.save(update_fields=["status", "error", "updated_at"])
        logger.warning("Failed to download %s: %s", item.identificador, exc)
        return item.status

    try:
        document, created = store_document(
            blob,
            title=item.titulo or item.identificador,
            description=_description_for(item),
            license="official_public",
            mime_type="application/pdf",
            source_type=Document.SourceType.OFFICIAL,
            visibility=Document.Visibility.PUBLIC,
            moderation_status=Document.ModerationStatus.PENDING,
            oposiciones=list(item.matched_oposiciones.all()),
        )
    except Exception as exc:  # storage or database failure: keep the ledger honest
        item.status = HarvestedItem.Status.FAILED
        item.error = f"{type(exc).__name__}: {exc}"
        item.save(update_fields=["status", "error", "updated_at"])
        logger.exception("Failed to store %s", item.identificador)
        return item.status

    item.document = document
    item.status = HarvestedItem.Status.IMPORTED if created else HarvestedItem.Status.DUPLICATE
    item.error = ""
    item.save(update_fields=["document", "status", "error", "updated_at"])
    return item.status


def _description_for(item: HarvestedItem) -> str:
    """A real description, so the page is not thin content on day one."""
    parts = [
        f"Publicado en el {item.get_boletin_display()} el "
        f"{item.fecha_publicacion.strftime('%d/%m/%Y')}.",
        f"Referencia: {item.identificador}.",
    ]
    if item.departamento:
        parts.append(f"Organismo: {item.departamento.title()}.")
    if item.epigrafe:
        parts.append(f"Epígrafe: {item.epigrafe}.")
    if item.url_html:
        parts.append(f"Texto oficial: {item.url_html}")
    return " ".join(parts)


# --- Scheduled entry points -------------------------------------------------


@shared_task(bind=True, max_retries=0)
def harvest_recent(self: object, days: int | None = None, boletin: str = Boletin.BOE) -> str:
    """Nightly task: harvest any recent day that has no completed run.

    Walks backwards over the catch-up window, so a night the server was down —
    or a night the lock was held by the backfill — is picked up automatically
    the next time this runs. That self-healing is why the window is days and
    not just "yesterday".
    """
    window = days if days is not None else settings.HARVEST_CATCHUP_DAYS
    if not _acquire_lock():
        logger.info("harvest_recent: another harvest holds the lock; standing down.")
        return "locked"

    processed = []
    try:
        today = timezone.localdate()
        for offset in range(1, window + 1):
            day = today - dt.timedelta(days=offset)
            existing = HarvestRun.objects.filter(boletin=boletin, fecha=day).first()
            if existing and existing.is_complete:
                continue
            harvest_day(day, boletin=boletin)
            processed.append(day.isoformat())
    finally:
        _release_lock()
    return f"harvested {len(processed)} day(s): {', '.join(processed) or 'none'}"


@shared_task(bind=True, max_retries=0)
def harvest_backfill(
    self: object,
    day: str | None = None,
    stop: str | None = None,
    boletin: str = Boletin.BOE,
) -> str:
    """Backfill one day, then queue itself for the day before.

    Walks backwards from ``day`` (default: yesterday) towards ``stop`` (default:
    ``HARVEST_BACKFILL_START``), newest first so the most useful content lands
    first and an interrupted backfill still leaves the site better off. The
    next day is enqueued only after this one finishes, with
    ``HARVEST_BACKFILL_COUNTDOWN`` seconds of breathing room in between.
    """
    stop_day = dt.date.fromisoformat(stop) if stop else default_backfill_start()
    current = dt.date.fromisoformat(day) if day else timezone.localdate() - dt.timedelta(days=1)
    if current < stop_day:
        logger.info("Backfill complete; reached %s", stop_day)
        return f"complete at {stop_day.isoformat()}"

    if not _acquire_lock():
        # The nightly job is mid-flight. Try this same day again shortly; the
        # backfill is not in a hurry.
        harvest_backfill.apply_async(
            kwargs={"day": current.isoformat(), "stop": stop_day.isoformat(), "boletin": boletin},
            countdown=settings.HARVEST_BACKFILL_COUNTDOWN,
            queue="harvest",
        )
        return f"locked, retrying {current.isoformat()}"

    try:
        run = HarvestRun.objects.filter(boletin=boletin, fecha=current).first()
        if not (run and run.is_complete):
            harvest_day(current, boletin=boletin)
    finally:
        _release_lock()

    next_day = current - dt.timedelta(days=1)
    if next_day >= stop_day:
        harvest_backfill.apply_async(
            kwargs={
                "day": next_day.isoformat(),
                "stop": stop_day.isoformat(),
                "boletin": boletin,
            },
            countdown=settings.HARVEST_BACKFILL_COUNTDOWN,
            queue="harvest",
        )
    return f"harvested {current.isoformat()}"


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def harvest_single_item(self: object, item_id: int) -> str:
    """Re-download one ledger item. Used by the admin retry action."""
    item = HarvestedItem.objects.get(pk=item_id)
    if item.status == HarvestedItem.Status.IMPORTED:
        return "already imported"
    item.status = HarvestedItem.Status.NEW
    item.save(update_fields=["status", "updated_at"])
    return import_item(item)
