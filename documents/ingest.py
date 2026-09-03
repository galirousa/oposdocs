"""Single entry point for putting a file into storage and the pipeline.

Three call sites need identical behaviour — the user upload view, the admin
document form and the automated source harvester — so the SHA-256 dedupe, the
content-addressed write and the pipeline kick-off live here instead of being
reimplemented (and drifting) per caller.
"""

import hashlib
from collections.abc import Iterable

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils.text import Truncator

from oposiciones.models import Convocatoria, Oposicion, Tema

from .models import Document
from .tasks import start_pipeline

TITLE_MAX_LENGTH = 300


def sha256_of(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def store_document(
    blob: bytes,
    *,
    title: str,
    license: str,
    mime_type: str,
    source_type: str = Document.SourceType.EDITORIAL,
    visibility: str = Document.Visibility.PUBLIC,
    moderation_status: str = Document.ModerationStatus.PENDING,
    description: str = "",
    uploader: object | None = None,
    convocatoria: Convocatoria | None = None,
    oposiciones: Iterable[Oposicion] = (),
    temas: Iterable[Tema] = (),
    run_pipeline: bool = True,
) -> tuple[Document, bool]:
    """Store ``blob`` and return ``(document, created)``.

    Dedupe is by content hash: an identical file already in the library yields
    the existing ``Document`` with ``created=False``, and nothing is written or
    re-processed. Callers decide what to do with a duplicate (the upload view
    shows it to the user, the harvester records it against the ledger row).
    """
    digest = sha256_of(blob)
    existing = Document.objects.filter(sha256=digest).first()
    if existing:
        return existing, False

    document = Document(
        title=Truncator(title).chars(TITLE_MAX_LENGTH),
        description=description,
        uploader=uploader,
        source_type=source_type,
        visibility=visibility,
        moderation_status=moderation_status,
        sha256=digest,
        storage_key=Document.storage_key_for(digest),
        mime_type=mime_type,
        size_bytes=len(blob),
        license=license,
        convocatoria=convocatoria,
    )
    try:
        with transaction.atomic():
            document.save()
    except IntegrityError:
        # Lost a race on the unique sha256; the winner's row is what we want.
        winner = Document.objects.filter(sha256=digest).first()
        if winner is None:
            raise
        return winner, False

    if oposiciones:
        document.oposiciones.set(oposiciones)
    if temas:
        document.temas.set(temas)
    default_storage.save(document.storage_key, ContentFile(blob))
    if run_pipeline:
        start_pipeline(document.pk)
    return document, True
