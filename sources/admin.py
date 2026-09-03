from typing import Any

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html

from .models import HarvestedItem, HarvestRule, HarvestRun
from .tasks import harvest_is_running, import_item


@admin.register(HarvestRule)
class HarvestRuleAdmin(admin.ModelAdmin):
    list_display = ("oposicion", "term_summary", "departamento_contiene", "is_active")
    list_filter = ("is_active", "oposicion__ambito")
    search_fields = ("oposicion__nombre", "terminos", "departamento_contiene")
    autocomplete_fields = ("oposicion",)

    @admin.display(description="Términos")
    def term_summary(self, obj: HarvestRule) -> str:
        terms = obj.term_list()
        shown = ", ".join(terms[:4])
        return f"{shown}…" if len(terms) > 4 else shown or "—"


@admin.register(HarvestRun)
class HarvestRunAdmin(admin.ModelAdmin):
    """Read-only: runs are written by the harvester, never by hand."""

    list_display = (
        "fecha",
        "boletin",
        "status",
        "items_seen",
        "items_imported",
        "items_duplicate",
        "items_failed",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "boletin")
    date_hierarchy = "fecha"

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def changelist_view(self, request: HttpRequest, extra_context: dict | None = None) -> Any:
        if harvest_is_running():
            self.message_user(
                request,
                "Hay una captura en curso ahora mismo (el candado está tomado).",
                messages.INFO,
            )
        return super().changelist_view(request, extra_context)


@admin.register(HarvestedItem)
class HarvestedItemAdmin(admin.ModelAdmin):
    list_display = (
        "identificador",
        "fecha_publicacion",
        "short_title",
        "departamento",
        "status",
        "document_link",
    )
    list_filter = ("status", "boletin", "seccion")
    search_fields = ("identificador", "titulo", "departamento")
    date_hierarchy = "fecha_publicacion"
    filter_horizontal = ("matched_oposiciones",)
    readonly_fields = (
        "identificador",
        "boletin",
        "fecha_publicacion",
        "seccion",
        "departamento",
        "epigrafe",
        "titulo",
        "url_pdf",
        "url_html",
        "url_xml",
        "size_bytes",
        "document",
        "error",
        "created_at",
        "updated_at",
    )
    actions = ["retry_import", "mark_ignored"]

    @admin.display(description="Título")
    def short_title(self, obj: HarvestedItem) -> str:
        return obj.titulo[:110] + ("…" if len(obj.titulo) > 110 else "")

    @admin.display(description="Documento")
    def document_link(self, obj: HarvestedItem) -> str:
        if not obj.document_id:
            return "—"
        url = reverse("admin:documents_document_change", args=[obj.document_id])
        return format_html('<a href="{}">{}</a>', url, obj.document.title[:60])

    @admin.action(description="Reintentar la descarga de los items seleccionados")
    def retry_import(self, request: HttpRequest, queryset: QuerySet) -> None:
        done = 0
        for item in queryset.exclude(status=HarvestedItem.Status.IMPORTED):
            item.status = HarvestedItem.Status.NEW
            item.save(update_fields=["status", "updated_at"])
            import_item(item)
            done += 1
        self.message_user(request, f"{done} item(s) reprocesados.", messages.SUCCESS)

    @admin.action(description="Ignorar los items seleccionados")
    def mark_ignored(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(status=HarvestedItem.Status.IGNORED)
        self.message_user(request, f"{updated} item(s) ignorados.", messages.WARNING)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
