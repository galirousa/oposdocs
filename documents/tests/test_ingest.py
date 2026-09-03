"""The shared ingest path: content-addressed storage plus SHA-256 dedupe."""

from unittest import mock

import pytest
from django.core.files.storage import default_storage

from documents.ingest import store_document
from documents.models import Document

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_pipeline():
    with mock.patch("documents.ingest.start_pipeline") as started:
        yield started


def _store(blob=b"%PDF-one", **kwargs):
    defaults = {
        "title": "Resolución de convocatoria",
        "license": "official_public",
        "mime_type": "application/pdf",
    }
    return store_document(blob, **{**defaults, **kwargs})


class TestStoreDocument:
    def test_stores_the_file_under_its_hash(self):
        document, created = _store()
        assert created
        assert document.storage_key == Document.storage_key_for(document.sha256)
        assert default_storage.exists(document.storage_key)
        assert document.size_bytes == len(b"%PDF-one")

    def test_identical_bytes_return_the_existing_document(self):
        first, created_first = _store()
        second, created_second = _store(title="Otro título")
        assert created_first and not created_second
        assert first.pk == second.pk
        assert Document.objects.count() == 1

    def test_pipeline_runs_once_per_new_document(self, _no_pipeline):
        _store()
        _store()
        assert _no_pipeline.call_count == 1

    def test_pipeline_can_be_suppressed(self, _no_pipeline):
        _store(run_pipeline=False)
        _no_pipeline.assert_not_called()

    def test_overlong_titles_are_truncated_to_fit(self):
        document, _ = _store(title="Resolución " * 60)
        assert len(document.title) <= 300
        assert document.slug

    def test_defaults_to_pending_moderation(self):
        """Nothing this helper stores is public until somebody approves it."""
        document, _ = _store()
        assert document.moderation_status == Document.ModerationStatus.PENDING
        assert not document.is_publicly_visible
