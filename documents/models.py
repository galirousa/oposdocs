from typing import Any

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models.functions import Left
from django.urls import reverse
from django.utils.text import slugify

from oposiciones.models import Convocatoria, Oposicion, Tema

LICENSE_CHOICES = [
    ("own_work", "Obra propia del autor"),
    ("official_public", "Documento oficial de libre reutilización"),
    ("permission_granted", "Con permiso del titular de los derechos"),
]

LICENSE_URLS = {
    "official_public": "https://www.boe.es/legislacion/aviso_legal.php",
}


class Document(models.Model):
    """A study document.

    ``source_type``, ``visibility`` and ``moderation_status`` are THREE
    INDEPENDENT AXES (see infrastructure plan §4). Never collapse them: a user
    document can be public, an official document can be temporarily private,
    and a rejected document is neither.
    """

    class SourceType(models.TextChoices):
        OFFICIAL = "official", "Oficial (BOE, ministerio)"
        EDITORIAL = "editorial", "Editorial (elaborado por la redacción)"
        USER = "user", "Aportado por un usuario"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Público"
        REGISTERED = "registered", "Solo usuarios registrados"
        PRIVATE = "private", "Privado"

    class ModerationStatus(models.TextChoices):
        PENDING = "pending", "Pendiente de revisión"
        APPROVED = "approved", "Aprobado"
        REJECTED = "rejected", "Rechazado"
        FLAGGED = "flagged", "Señalado"
        TAKEN_DOWN = "taken_down", "Retirado"

    class ExtractionStatus(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PROCESSING = "processing", "En proceso"
        OCR_QUEUED = "ocr_queued", "En cola de OCR"
        DONE = "done", "Completada"
        FAILED = "failed", "Fallida"
        SKIPPED = "skipped", "Omitida"

    title = models.CharField("título", max_length=300)
    slug = models.SlugField("slug", max_length=320, unique=True, blank=True)
    description = models.TextField("descripción", blank=True)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        verbose_name="autor de la subida",
    )
    source_type = models.CharField(
        "origen", max_length=10, choices=SourceType.choices, default=SourceType.EDITORIAL
    )
    visibility = models.CharField(
        "visibilidad", max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    moderation_status = models.CharField(
        "estado de moderación",
        max_length=10,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
    )
    storage_key = models.CharField("clave de almacenamiento", max_length=300, blank=True)
    sha256 = models.CharField("SHA-256", max_length=64, unique=True, db_index=True)
    mime_type = models.CharField("tipo MIME", max_length=100, blank=True)
    size_bytes = models.BigIntegerField("tamaño en bytes", default=0)
    page_count = models.PositiveIntegerField("número de páginas", null=True, blank=True)
    extracted_text = models.TextField("texto extraído", blank=True)
    extraction_status = models.CharField(
        "estado de extracción",
        max_length=12,
        choices=ExtractionStatus.choices,
        default=ExtractionStatus.PENDING,
    )
    license = models.CharField("licencia", max_length=20, choices=LICENSE_CHOICES)
    download_count = models.PositiveIntegerField("descargas", default=0)
    # Denormalised tema/oposición names for search weight B; refreshed by the
    # indexing task so the generated search_vector can include them.
    tags_text = models.TextField("etiquetas (denormalizado)", blank=True, editable=False)
    # When the same file serves several oposiciones under different entries,
    # non-canonical copies point here and their pages canonicalise to it.
    canonical_document = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
        verbose_name="documento canónico",
    )
    oposiciones = models.ManyToManyField(
        Oposicion, blank=True, related_name="documents", verbose_name="oposiciones"
    )
    temas = models.ManyToManyField(Tema, blank=True, related_name="documents", verbose_name="temas")
    convocatoria = models.ForeignKey(
        Convocatoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        verbose_name="convocatoria",
    )
    created_at = models.DateTimeField("fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("última modificación", auto_now=True)

    search_vector = models.GeneratedField(
        expression=(
            SearchVector("title", weight="A", config="es_unaccent")
            + SearchVector("tags_text", weight="B", config="es_unaccent")
            + SearchVector("description", weight="C", config="es_unaccent")
            + SearchVector(Left("extracted_text", 150000), weight="D", config="es_unaccent")
        ),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["-created_at"]
        indexes = [
            GinIndex(name="document_search_gin", fields=["search_vector"]),
            GinIndex(name="document_title_trgm", fields=["title"], opclasses=["gin_trgm_ops"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            base = slugify(self.title)[:280] or "documento"
            slug = base
            n = 2
            while Document.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    # --- Storage layout (content-addressed) --------------------------------

    @staticmethod
    def storage_key_for(sha256: str) -> str:
        return f"documents/{sha256[:2]}/{sha256}"

    @property
    def thumbnail_key(self) -> str:
        return f"thumbs/{self.sha256}.webp"

    # --- Indexability -------------------------------------------------------

    @property
    def is_thin(self) -> bool:
        """Thin content guard: no description and no extracted text means the
        page is an empty shell that would damage sitewide rankings."""
        return not self.description.strip() and not self.extracted_text.strip()

    @property
    def is_indexable(self) -> bool:
        return (
            self.visibility == self.Visibility.PUBLIC
            and self.moderation_status == self.ModerationStatus.APPROVED
            and not self.is_thin
            and self.canonical_document_id is None
        )

    @property
    def is_publicly_visible(self) -> bool:
        return (
            self.visibility == self.Visibility.PUBLIC
            and self.moderation_status == self.ModerationStatus.APPROVED
        )

    @property
    def license_url(self) -> str | None:
        return LICENSE_URLS.get(self.license)

    @property
    def text_preview(self) -> str:
        """First ~500 words of extracted text, rendered in the initial HTML."""
        words = self.extracted_text.split()
        preview = " ".join(words[:500])
        if len(words) > 500:
            preview += " …"
        return preview

    def facts(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = [
            ("Origen", self.get_source_type_display()),
            ("Licencia", self.get_license_display()),
        ]
        if self.mime_type:
            rows.append(("Formato", self.mime_type))
        if self.page_count:
            rows.append(("Páginas", str(self.page_count)))
        if self.size_bytes:
            rows.append(("Tamaño", f"{self.size_bytes / (1024 * 1024):.1f} MB"))
        first = self.oposiciones.first()
        if first:
            rows.append(("Oposición", first.derived_title))
        rows.append(("Publicado", self.created_at.strftime("%d/%m/%Y")))
        return rows

    def get_absolute_url(self) -> str:
        return reverse("documents:detail", kwargs={"slug": self.slug})


class Report(models.Model):
    """A takedown/abuse report; the LSSI safe harbour depends on acting on these."""

    class Reason(models.TextChoices):
        COPYRIGHT = "copyright", "Infracción de derechos de autor"
        INCORRECT = "incorrect", "Contenido incorrecto"
        INAPPROPRIATE = "inappropriate", "Contenido inapropiado"
        DUPLICATE = "duplicate", "Duplicado"

    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        REVIEWING = "reviewing", "En revisión"
        RESOLVED = "resolved", "Resuelta"
        DISMISSED = "dismissed", "Desestimada"

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="reports", verbose_name="documento"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
        verbose_name="denunciante",
    )
    contact_email = models.EmailField("email de contacto", blank=True)
    reason = models.CharField("motivo", max_length=15, choices=Reason.choices)
    detail = models.TextField("detalle")
    status = models.CharField("estado", max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField("fecha", auto_now_add=True)
    updated_at = models.DateTimeField("última modificación", auto_now=True)

    class Meta:
        verbose_name = "denuncia"
        verbose_name_plural = "denuncias"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_reason_display()} — {self.document}"


class ModerationLog(models.Model):
    """Immutable audit trail: who changed what status, when and why."""

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="moderation_log",
        verbose_name="documento",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="autor del cambio",
    )
    from_status = models.CharField("estado anterior", max_length=10)
    to_status = models.CharField("estado nuevo", max_length=10)
    reason = models.TextField("motivo", blank=True)
    created_at = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "registro de moderación"
        verbose_name_plural = "registros de moderación"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.document_id}: {self.from_status} → {self.to_status}"
