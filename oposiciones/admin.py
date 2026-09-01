from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Convocatoria, Oposicion, Tema


class ConvocatoriaInline(admin.TabularInline):
    model = Convocatoria
    extra = 0
    fields = (
        "anio",
        "estado",
        "plazas",
        "referencia_boe",
        "fecha_publicacion",
        "fecha_limite_solicitud",
    )


class TemaInline(admin.TabularInline):
    model = Tema
    extra = 0
    fields = ("numero", "bloque", "titulo")


@admin.register(Oposicion)
class OposicionAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "ambito",
        "comunidad",
        "grupo",
        "is_published",
        "is_featured",
        "homepage_order",
    )
    list_filter = ("ambito", "comunidad", "grupo", "is_featured", "is_published")
    list_editable = ("is_featured", "homepage_order")
    search_fields = ("nombre", "cuerpo", "escala", "slug")
    inlines = [ConvocatoriaInline, TemaInline]
    actions = ["marcar_destacadas", "quitar_destacadas", "publicar"]
    prepopulated_fields: dict[str, tuple[str, ...]] = {}

    def get_readonly_fields(
        self, request: HttpRequest, obj: Oposicion | None = None
    ) -> tuple[str, ...]:
        # The slug is immutable once published: read-only in the admin so an
        # editor cannot break earned inbound links by accident.
        base = ("created_at", "updated_at")
        if obj and obj.is_published:
            return ("slug", *base)
        return base

    @admin.action(description="Destacar en portada")
    def marcar_destacadas(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(is_featured=True)

    @admin.action(description="Quitar de portada")
    def quitar_destacadas(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(is_featured=False)

    @admin.action(description="Publicar")
    def publicar(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(is_published=True)


@admin.register(Convocatoria)
class ConvocatoriaAdmin(admin.ModelAdmin):
    list_display = ("oposicion", "anio", "estado", "plazas", "fecha_limite_solicitud")
    list_filter = ("estado", "anio")
    search_fields = ("oposicion__nombre", "referencia_boe")
    autocomplete_fields = ("oposicion",)


@admin.register(Tema)
class TemaAdmin(admin.ModelAdmin):
    list_display = ("oposicion", "numero", "titulo", "bloque")
    list_filter = ("oposicion",)
    search_fields = ("titulo",)
    autocomplete_fields = ("oposicion",)
