from datetime import date
from typing import Any

from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

COMUNIDADES = [
    ("andalucia", "Andalucía"),
    ("aragon", "Aragón"),
    ("asturias", "Principado de Asturias"),
    ("baleares", "Illes Balears"),
    ("canarias", "Canarias"),
    ("cantabria", "Cantabria"),
    ("castilla-la-mancha", "Castilla-La Mancha"),
    ("castilla-y-leon", "Castilla y León"),
    ("cataluna", "Cataluña"),
    ("ceuta", "Ceuta"),
    ("comunidad-valenciana", "Comunitat Valenciana"),
    ("extremadura", "Extremadura"),
    ("galicia", "Galicia"),
    ("la-rioja", "La Rioja"),
    ("madrid", "Comunidad de Madrid"),
    ("melilla", "Melilla"),
    ("murcia", "Región de Murcia"),
    ("navarra", "Comunidad Foral de Navarra"),
    ("pais-vasco", "País Vasco"),
]


class Oposicion(models.Model):
    class Ambito(models.TextChoices):
        ESTADO = "estado", "Estatal"
        AUTONOMICA = "autonomica", "Autonómica"
        LOCAL = "local", "Local"

    class Grupo(models.TextChoices):
        A1 = "A1", "A1"
        A2 = "A2", "A2"
        B = "B", "B"
        C1 = "C1", "C1"
        C2 = "C2", "C2"
        E = "E", "E (agrupaciones profesionales)"

    class SistemaSelectivo(models.TextChoices):
        OPOSICION = "oposicion", "Oposición"
        CONCURSO_OPOSICION = "concurso-oposicion", "Concurso-oposición"
        CONCURSO = "concurso", "Concurso"

    slug = models.SlugField("slug", max_length=200, unique=True, blank=True)
    nombre = models.CharField("nombre", max_length=200)
    ambito = models.CharField("ámbito", max_length=20, choices=Ambito.choices)
    comunidad = models.CharField(
        "comunidad autónoma",
        max_length=30,
        choices=COMUNIDADES,
        blank=True,
        help_text="Solo para oposiciones autonómicas o locales.",
    )
    cuerpo = models.CharField("cuerpo", max_length=200, blank=True)
    escala = models.CharField("escala", max_length=200, blank=True)
    grupo = models.CharField("grupo", max_length=2, choices=Grupo.choices)
    titulacion_requerida = models.CharField("titulación requerida", max_length=300, blank=True)
    sistema_selectivo = models.CharField(
        "sistema selectivo",
        max_length=20,
        choices=SistemaSelectivo.choices,
        default=SistemaSelectivo.OPOSICION,
    )
    organismo_convocante = models.CharField("organismo convocante", max_length=300, blank=True)
    descripcion = models.TextField("descripción", blank=True)
    is_featured = models.BooleanField("destacada en portada", default=False)
    homepage_order = models.IntegerField("orden en portada", default=0)
    is_published = models.BooleanField("publicada", default=False)
    created_at = models.DateTimeField("fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("última modificación", auto_now=True)

    class Meta:
        verbose_name = "oposición"
        verbose_name_plural = "oposiciones"
        ordering = ["homepage_order", "nombre"]
        indexes = [
            GinIndex(
                name="oposicion_nombre_trgm",
                fields=["nombre"],
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __str__(self) -> str:
        return self.derived_title

    # --- Slugs: auto-generated, unique, immutable once published -----------

    def _build_slug(self) -> str:
        base = slugify(self.nombre)
        candidates = [base]
        if self.comunidad:
            candidates.append(f"{base}-{slugify(self.comunidad)}")
        candidates.append(f"{base}-{slugify(self.ambito)}")
        for candidate in candidates:
            if not Oposicion.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                return candidate
        n = 2
        while Oposicion.objects.exclude(pk=self.pk).filter(slug=f"{base}-{n}").exists():
            n += 1
        return f"{base}-{n}"

    def clean(self) -> None:
        if self.pk:
            old = Oposicion.objects.filter(pk=self.pk).values("slug", "is_published").first()
            if old and old["is_published"] and self.slug and self.slug != old["slug"]:
                raise ValidationError(
                    {
                        "slug": (
                            "El slug es inmutable una vez publicada la oposición: "
                            "cambiarlo rompería todos los enlaces entrantes y el "
                            "posicionamiento ganado."
                        )
                    }
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = self._build_slug()
        if self.pk:
            old = Oposicion.objects.filter(pk=self.pk).values("slug", "is_published").first()
            if old and old["is_published"] and self.slug != old["slug"]:
                # Belt and braces: clean() surfaces this in forms, this guard
                # catches programmatic writes that skip validation.
                self.slug = old["slug"]
        super().save(*args, **kwargs)

    # --- Derived presentation ----------------------------------------------

    @property
    def comunidad_display(self) -> str:
        return dict(COMUNIDADES).get(self.comunidad, "")

    @property
    def derived_title(self) -> str:
        """Natural Spanish name users actually search for (H1 and <title>)."""
        nombre = self.nombre.strip()
        lowered = nombre.lower()
        if self.ambito == self.Ambito.ESTADO:
            if "estado" in lowered or "nacional" in lowered or "civil" in lowered:
                return nombre
            return f"{nombre} del Estado"
        if self.ambito == self.Ambito.AUTONOMICA and self.comunidad:
            if self.comunidad_display.lower() in lowered:
                return nombre
            return f"{nombre} de la {self.comunidad_display}"
        return nombre

    @property
    def current_convocatoria(self) -> "Convocatoria | None":
        return self.convocatorias.order_by("-anio", "-fecha_publicacion").first()

    @property
    def answer_paragraph(self) -> str:
        """Answer-first paragraph: factual prose that stands alone when
        extracted with no surrounding page context."""
        parts: list[str] = []
        organismo = self.organismo_convocante or "la Administración General del Estado"
        parts.append(
            f"La oposición a {self.derived_title} es un proceso selectivo de "
            f"ámbito {self.get_ambito_display().lower()} convocado por {organismo} "
            f"para el acceso al grupo {self.grupo} de la función pública"
        )
        if self.cuerpo:
            parts[-1] += f", en el {self.cuerpo}"
        parts[-1] += "."
        if self.titulacion_requerida:
            parts.append(f"Para presentarse se exige {self.titulacion_requerida.lower()}.")
        parts.append(f"El sistema selectivo es de {self.get_sistema_selectivo_display().lower()}.")
        conv = self.current_convocatoria
        if conv:
            estado = conv.get_estado_display().lower()
            frase = f"La convocatoria de {conv.anio} se encuentra {estado}"
            if conv.plazas:
                frase += f", con {conv.plazas} plazas"
            if (
                conv.estado == Convocatoria.Estado.ABIERTA
                and conv.fecha_limite_solicitud
                and conv.fecha_limite_solicitud >= date.today()
            ):
                frase += (
                    " y plazo de solicitud abierto hasta el "
                    f"{conv.fecha_limite_solicitud.strftime('%d/%m/%Y')}"
                )
            parts.append(frase + ".")
        else:
            parts.append("Actualmente no consta ninguna convocatoria registrada.")
        return " ".join(parts)

    def facts(self) -> list[tuple[str, str]]:
        """Single source for the visible facts block, the markdown table and
        the JSON-LD payload: never let them diverge."""
        rows: list[tuple[str, str]] = [
            ("Ámbito", self.get_ambito_display()),
            ("Grupo", self.grupo),
            ("Sistema selectivo", self.get_sistema_selectivo_display()),
        ]
        if self.comunidad:
            rows.insert(1, ("Comunidad", self.comunidad_display))
        if self.cuerpo:
            rows.append(("Cuerpo", self.cuerpo))
        if self.escala:
            rows.append(("Escala", self.escala))
        if self.titulacion_requerida:
            rows.append(("Titulación requerida", self.titulacion_requerida))
        if self.organismo_convocante:
            rows.append(("Organismo convocante", self.organismo_convocante))
        conv = self.current_convocatoria
        if conv:
            estado = f"{conv.get_estado_display()} ({conv.anio})"
            rows.append(("Última convocatoria", estado))
            if conv.plazas:
                rows.append(("Plazas", str(conv.plazas)))
        return rows

    def get_absolute_url(self) -> str:
        return reverse("oposiciones:detail", kwargs={"ambito": self.ambito, "slug": self.slug})


class Convocatoria(models.Model):
    class Estado(models.TextChoices):
        ANUNCIADA = "anunciada", "Anunciada"
        ABIERTA = "abierta", "Abierta"
        CERRADA = "cerrada", "Cerrada"
        EN_PROCESO = "en_proceso", "En proceso"
        RESUELTA = "resuelta", "Resuelta"

    oposicion = models.ForeignKey(
        Oposicion,
        on_delete=models.CASCADE,
        related_name="convocatorias",
        verbose_name="oposición",
    )
    slug = models.SlugField("slug", max_length=220, blank=True)
    anio = models.PositiveIntegerField("año")
    referencia_boe = models.CharField("referencia BOE", max_length=100, blank=True)
    url_boe = models.URLField("URL del BOE", blank=True)
    plazas = models.PositiveIntegerField("plazas", null=True, blank=True)
    plazas_libre = models.PositiveIntegerField("plazas turno libre", null=True, blank=True)
    plazas_discapacidad = models.PositiveIntegerField(
        "plazas reserva discapacidad", null=True, blank=True
    )
    fecha_publicacion = models.DateField("fecha de publicación", null=True, blank=True)
    fecha_limite_solicitud = models.DateField("fecha límite de solicitud", null=True, blank=True)
    estado = models.CharField(
        "estado", max_length=20, choices=Estado.choices, default=Estado.ANUNCIADA
    )
    notas = models.TextField("notas", blank=True)
    created_at = models.DateTimeField("fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("última modificación", auto_now=True)

    class Meta:
        verbose_name = "convocatoria"
        verbose_name_plural = "convocatorias"
        ordering = ["-anio", "-fecha_publicacion"]
        constraints = [
            models.UniqueConstraint(fields=["anio", "slug"], name="convocatoria_anio_slug"),
        ]

    def __str__(self) -> str:
        return f"{self.oposicion.derived_title} — convocatoria {self.anio}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            base = self.oposicion.slug
            slug = base
            if Convocatoria.objects.exclude(pk=self.pk).filter(anio=self.anio, slug=slug).exists():
                suffix = slugify(self.referencia_boe) or "bis"
                slug = f"{base}-{suffix}"[:220]
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def descripcion_jobposting(self) -> str:
        op = self.oposicion
        desc = f"Convocatoria {self.anio} de la oposición a {op.derived_title} (grupo {op.grupo})."
        if self.plazas:
            desc += f" {self.plazas} plazas convocadas."
        if self.referencia_boe:
            desc += f" Publicada en el BOE ({self.referencia_boe})."
        if op.titulacion_requerida:
            desc += f" Titulación requerida: {op.titulacion_requerida}."
        return desc

    def facts(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = [
            ("Oposición", self.oposicion.derived_title),
            ("Año", str(self.anio)),
            ("Estado", self.get_estado_display()),
        ]
        if self.plazas is not None:
            rows.append(("Plazas", str(self.plazas)))
        if self.plazas_libre is not None:
            rows.append(("Plazas turno libre", str(self.plazas_libre)))
        if self.plazas_discapacidad is not None:
            rows.append(("Reserva discapacidad", str(self.plazas_discapacidad)))
        if self.referencia_boe:
            rows.append(("Referencia BOE", self.referencia_boe))
        if self.fecha_publicacion:
            rows.append(("Publicación", self.fecha_publicacion.strftime("%d/%m/%Y")))
        if self.fecha_limite_solicitud:
            rows.append(("Límite de solicitud", self.fecha_limite_solicitud.strftime("%d/%m/%Y")))
        return rows

    def get_absolute_url(self) -> str:
        return reverse(
            "oposiciones:convocatoria_detail",
            kwargs={"anio": self.anio, "slug": self.slug},
        )


class Tema(models.Model):
    oposicion = models.ForeignKey(
        Oposicion, on_delete=models.CASCADE, related_name="temas", verbose_name="oposición"
    )
    numero = models.PositiveIntegerField("número")
    titulo = models.CharField("título", max_length=500)
    bloque = models.CharField("bloque", max_length=200, blank=True)

    class Meta:
        verbose_name = "tema"
        verbose_name_plural = "temas"
        ordering = ["oposicion", "numero"]
        constraints = [
            models.UniqueConstraint(fields=["oposicion", "numero"], name="tema_unico_numero"),
        ]

    def __str__(self) -> str:
        return f"Tema {self.numero}. {self.titulo}"
