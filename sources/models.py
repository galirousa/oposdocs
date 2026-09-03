"""Ledger for automated harvesting of official bulletins.

The ledger exists so that a nightly job is *idempotent and observable*: every
item the BOE published is a row, whether or not it became a Document, so a
re-run costs one HTTP request instead of re-downloading a day of PDFs, and a
silent failure shows up in the admin instead of merely as absent content.
"""

import datetime as dt
import unicodedata

from django.db import models

from oposiciones.models import Oposicion


class Boletin(models.TextChoices):
    """Bulletins we harvest. BOE first; the autonomous bulletins (DOG, BOJA,
    BOCM…) reuse the ledger and only need their own client module."""

    BOE = "boe", "BOE (Boletín Oficial del Estado)"


def normalize(text: str) -> str:
    """Lowercase and strip accents, so «oposición» matches «OPOSICION»."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


class HarvestRule(models.Model):
    """Attaches harvested items to an oposición by keyword.

    Deliberately dumb: an editor writes the terms, and anything that does not
    match stays in the queue for a human. Guessing wrongly here would attach an
    official document to the wrong oposición on a public page.
    """

    oposicion = models.ForeignKey(
        Oposicion,
        on_delete=models.CASCADE,
        related_name="harvest_rules",
        verbose_name="oposición",
    )
    terminos = models.TextField(
        "términos",
        help_text=(
            "Un término por línea. El item coincide si su título contiene "
            "alguno de ellos (sin distinguir mayúsculas ni acentos)."
        ),
    )
    departamento_contiene = models.CharField(
        "el departamento contiene",
        max_length=200,
        blank=True,
        help_text="Opcional. Restringe la regla a un organismo convocante.",
    )
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("última modificación", auto_now=True)

    class Meta:
        verbose_name = "regla de captura"
        verbose_name_plural = "reglas de captura"
        ordering = ["oposicion__nombre"]

    def __str__(self) -> str:
        return f"{self.oposicion} ← {self.term_list()[:3]}"

    def term_list(self) -> list[str]:
        return [line.strip() for line in self.terminos.splitlines() if line.strip()]

    def matches(self, titulo: str, departamento: str) -> bool:
        if not self.is_active:
            return False
        if self.departamento_contiene and normalize(self.departamento_contiene) not in normalize(
            departamento
        ):
            return False
        haystack = normalize(titulo)
        return any(normalize(term) in haystack for term in self.term_list())


class HarvestRun(models.Model):
    """One attempt at one day of one bulletin. Unique per (boletin, fecha) so a
    re-run updates the record rather than growing a pile of duplicates."""

    class Status(models.TextChoices):
        RUNNING = "running", "En curso"
        OK = "ok", "Completada"
        NO_EDITION = "no_edition", "Sin edición"
        FAILED = "failed", "Fallida"

    boletin = models.CharField(
        "boletín", max_length=10, choices=Boletin.choices, default=Boletin.BOE
    )
    fecha = models.DateField("fecha del boletín")
    status = models.CharField(
        "estado", max_length=12, choices=Status.choices, default=Status.RUNNING
    )
    items_seen = models.PositiveIntegerField("items encontrados", default=0)
    items_imported = models.PositiveIntegerField("documentos importados", default=0)
    items_duplicate = models.PositiveIntegerField("duplicados", default=0)
    items_failed = models.PositiveIntegerField("fallidos", default=0)
    error = models.TextField("error", blank=True)
    started_at = models.DateTimeField("inicio", auto_now_add=True)
    finished_at = models.DateTimeField("fin", null=True, blank=True)

    class Meta:
        verbose_name = "ejecución de captura"
        verbose_name_plural = "ejecuciones de captura"
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(fields=["boletin", "fecha"], name="one_run_per_bulletin_day")
        ]

    def __str__(self) -> str:
        return f"{self.get_boletin_display()} {self.fecha} ({self.status})"

    @property
    def is_complete(self) -> bool:
        return self.status in (self.Status.OK, self.Status.NO_EDITION)


class HarvestedItem(models.Model):
    """One item from a bulletin summary, and what became of it."""

    class Status(models.TextChoices):
        NEW = "new", "Pendiente de descarga"
        IMPORTED = "imported", "Importado"
        DUPLICATE = "duplicate", "Duplicado (ya existía)"
        IGNORED = "ignored", "Ignorado"
        FAILED = "failed", "Fallido"

    boletin = models.CharField(
        "boletín", max_length=10, choices=Boletin.choices, default=Boletin.BOE
    )
    identificador = models.CharField("identificador", max_length=50, unique=True, db_index=True)
    fecha_publicacion = models.DateField("fecha de publicación")
    seccion = models.CharField("sección", max_length=200, blank=True)
    departamento = models.CharField("departamento", max_length=300, blank=True)
    epigrafe = models.CharField("epígrafe", max_length=300, blank=True)
    titulo = models.TextField("título")
    url_pdf = models.URLField("URL del PDF", max_length=500, blank=True)
    url_html = models.URLField("URL HTML", max_length=500, blank=True)
    url_xml = models.URLField("URL XML", max_length=500, blank=True)
    size_bytes = models.BigIntegerField("tamaño anunciado", default=0)
    status = models.CharField("estado", max_length=10, choices=Status.choices, default=Status.NEW)
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="harvested_items",
        verbose_name="documento",
    )
    matched_oposiciones = models.ManyToManyField(
        Oposicion,
        blank=True,
        related_name="harvested_items",
        verbose_name="oposiciones detectadas",
    )
    error = models.TextField("error", blank=True)
    created_at = models.DateTimeField("fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("última modificación", auto_now=True)

    class Meta:
        verbose_name = "item capturado"
        verbose_name_plural = "items capturados"
        ordering = ["-fecha_publicacion", "identificador"]
        indexes = [
            models.Index(fields=["status", "fecha_publicacion"], name="item_status_fecha_idx"),
        ]

    def __str__(self) -> str:
        return self.identificador

    @property
    def pdf_filename(self) -> str:
        return f"{self.identificador}.pdf"

    def matching_rules(self) -> list[HarvestRule]:
        rules = HarvestRule.objects.filter(is_active=True).select_related("oposicion")
        return [rule for rule in rules if rule.matches(self.titulo, self.departamento)]


def default_backfill_start() -> dt.date:
    from django.conf import settings

    return dt.datetime.strptime(settings.HARVEST_BACKFILL_START, "%Y-%m-%d").date()
