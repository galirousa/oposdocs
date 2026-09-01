"""Document ingestion pipeline: chained Celery tasks, each independently
retryable. Failure degrades gracefully — a document with failed extraction
still exists and is findable by title and tags, just not by full text.
"""

import io
import logging
import socket
import subprocess
import tempfile
from pathlib import Path

from celery import chain, shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE = 100  # below this, extraction is considered failed → OCR


def start_pipeline(document_id: int) -> None:
    """Kick off the full chain for a freshly stored document."""
    chain(
        scan_document.si(document_id),
        extract_text.si(document_id),
        generate_thumbnail.si(document_id),
        index_document.si(document_id),
    ).apply_async()


def _download_to_tempfile(storage_key: str, suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)  # noqa: SIM115
    with default_storage.open(storage_key, "rb") as remote:
        for block in iter(lambda: remote.read(1024 * 1024), b""):
            handle.write(block)
    handle.close()
    return Path(handle.name)


def _clamav_scan_stream(data_path: Path) -> bool:
    """INSTREAM scan against clamd. Returns True when clean."""
    with socket.create_connection(
        (settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=120
    ) as sock:
        sock.sendall(b"zINSTREAM\0")
        with open(data_path, "rb") as fh:
            while block := fh.read(1024 * 512):
                sock.sendall(len(block).to_bytes(4, "big") + block)
        sock.sendall((0).to_bytes(4, "big"))
        response = sock.recv(4096).decode("utf-8", "replace")
    return "OK" in response and "FOUND" not in response


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scan_document(self: object, document_id: int) -> None:
    from .models import Document

    document = Document.objects.get(pk=document_id)
    if not settings.CLAMAV_HOST:
        logger.warning("ClamAV not configured; skipping virus scan for %s", document_id)
        return
    path = _download_to_tempfile(document.storage_key, ".bin")
    try:
        clean = _clamav_scan_stream(path)
    finally:
        path.unlink(missing_ok=True)
    if not clean:
        document.moderation_status = Document.ModerationStatus.REJECTED
        document.save(update_fields=["moderation_status", "updated_at"])
        raise RuntimeError(f"ClamAV flagged document {document_id}; rejected.")


def _pdf_page_count(path: Path) -> int | None:
    try:
        out = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, timeout=60, check=True
        ).stdout
        for line in out.splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None
    return None


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def extract_text(self: object, document_id: int) -> None:
    from .models import Document

    document = Document.objects.get(pk=document_id)
    document.extraction_status = Document.ExtractionStatus.PROCESSING
    document.save(update_fields=["extraction_status", "updated_at"])

    try:
        if document.mime_type == "application/pdf":
            path = _download_to_tempfile(document.storage_key, ".pdf")
            try:
                document.page_count = _pdf_page_count(path)
                result = subprocess.run(
                    ["pdftotext", "-enc", "UTF-8", str(path), "-"],
                    capture_output=True,
                    timeout=300,
                    check=False,
                )
                text = result.stdout.decode("utf-8", "replace").strip()
            finally:
                path.unlink(missing_ok=True)
        elif document.mime_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            import docx

            path = _download_to_tempfile(document.storage_key, ".docx")
            try:
                parsed = docx.Document(str(path))
                text = "\n".join(p.text for p in parsed.paragraphs).strip()
            finally:
                path.unlink(missing_ok=True)
        else:
            document.extraction_status = Document.ExtractionStatus.SKIPPED
            document.save(update_fields=["extraction_status", "updated_at"])
            return

        pages = document.page_count or 1
        if document.mime_type == "application/pdf" and len(text) < MIN_CHARS_PER_PAGE * pages:
            # Probably a scan without a text layer: queue OCR on the
            # low-priority queue (capped concurrency, page ceiling).
            document.extracted_text = text
            document.extraction_status = Document.ExtractionStatus.OCR_QUEUED
            document.save(
                update_fields=["extracted_text", "extraction_status", "page_count", "updated_at"]
            )
            ocr_document.apply_async(args=[document_id], queue="ocr")
            return

        document.extracted_text = text
        document.extraction_status = Document.ExtractionStatus.DONE
        document.save(
            update_fields=["extracted_text", "extraction_status", "page_count", "updated_at"]
        )
    except Exception:
        document.extraction_status = Document.ExtractionStatus.FAILED
        document.save(update_fields=["extraction_status", "updated_at"])
        logger.exception("Text extraction failed for document %s", document_id)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def ocr_document(self: object, document_id: int) -> None:
    """Tesseract OCR fallback (lang=spa), page-capped."""
    from .models import Document

    document = Document.objects.get(pk=document_id)
    if document.page_count and document.page_count > settings.OCR_MAX_PAGES:
        logger.warning(
            "Document %s has %s pages, over the OCR ceiling (%s); skipping.",
            document_id,
            document.page_count,
            settings.OCR_MAX_PAGES,
        )
        document.extraction_status = Document.ExtractionStatus.SKIPPED
        document.save(update_fields=["extraction_status", "updated_at"])
        return

    path = _download_to_tempfile(document.storage_key, ".pdf")
    texts: list[str] = []
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["pdftoppm", "-r", "200", "-png", str(path), f"{tmpdir}/page"],
                timeout=1800,
                check=True,
            )
            for png in sorted(Path(tmpdir).glob("page*.png")):
                result = subprocess.run(
                    ["tesseract", str(png), "-", "-l", settings.OCR_LANGUAGE],
                    capture_output=True,
                    timeout=300,
                    check=False,
                )
                texts.append(result.stdout.decode("utf-8", "replace"))
        document.extracted_text = "\n".join(texts).strip()
        document.extraction_status = Document.ExtractionStatus.DONE
        document.save(update_fields=["extracted_text", "extraction_status", "updated_at"])
        index_document.delay(document_id)
    except Exception:
        document.extraction_status = Document.ExtractionStatus.FAILED
        document.save(update_fields=["extraction_status", "updated_at"])
        logger.exception("OCR failed for document %s", document_id)
    finally:
        path.unlink(missing_ok=True)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def generate_thumbnail(self: object, document_id: int) -> None:
    from PIL import Image

    from .models import Document

    document = Document.objects.get(pk=document_id)
    if document.mime_type != "application/pdf":
        return
    path = _download_to_tempfile(document.storage_key, ".pdf")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    "1",
                    "-l",
                    "1",
                    "-scale-to",
                    "600",
                    "-png",
                    str(path),
                    f"{tmpdir}/thumb",
                ],
                timeout=120,
                check=True,
            )
            pages = sorted(Path(tmpdir).glob("thumb*.png"))
            if not pages:
                return
            buffer = io.BytesIO()
            Image.open(pages[0]).convert("RGB").save(buffer, "WEBP", quality=80)
            default_storage.save(document.thumbnail_key, ContentFile(buffer.getvalue()))
    except Exception:
        logger.exception("Thumbnail generation failed for document %s", document_id)
    finally:
        path.unlink(missing_ok=True)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def index_document(self: object, document_id: int) -> None:
    from search.backends import get_backend

    from .models import Document

    document = Document.objects.get(pk=document_id)
    get_backend().index(document)
