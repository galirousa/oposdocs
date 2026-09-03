from typing import Any

from django import forms
from django.contrib import admin, messages
from django.core.mail import send_mail
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from .models import Document, ModerationLog, Report


def _log_status_change(
    document: Document, actor: Any, from_status: str, to_status: str, reason: str = ""
) -> None:
    ModerationLog.objects.create(
        document=document,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
    )


class RejectActionForm(forms.Form):
    """Bulk rejection requires a reason, which is emailed to the uploader."""

    reason = forms.CharField(widget=forms.Textarea, required=True, label="Motivo del rechazo")


class DocumentAdminForm(forms.ModelForm):
    """Editors upload the file here; hashing, storage and the pipeline run on save."""

    archivo = forms.FileField(
        required=False,
        label="Archivo",
        help_text="PDF o DOCX. Obligatorio al crear un documento nuevo.",
    )

    class Meta:
        model = Document
        fields = (
            "title",
            "slug",
            "description",
            "uploader",
            "source_type",
            "visibility",
            "moderation_status",
            "mime_type",
            "page_count",
            "license",
            "canonical_document",
            "oposiciones",
            "temas",
            "convocatoria",
        )

    def clean(self) -> dict:
        from .ingest import sha256_of

        cleaned = super().clean()
        uploaded = cleaned.get("archivo")
        if not self.instance.pk and not uploaded:
            raise forms.ValidationError("Selecciona un archivo para el documento nuevo.")
        if uploaded:
            blob = uploaded.read()
            sha256 = sha256_of(blob)
            existing = Document.objects.exclude(pk=self.instance.pk).filter(sha256=sha256).first()
            if existing:
                raise forms.ValidationError(
                    f"Este archivo ya existe como «{existing.title}» (dedupe por SHA-256)."
                )
            self._blob = blob
            self._sha256 = sha256
        return cleaned


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentAdminForm
    list_display = (
        "title",
        "source_type",
        "visibility",
        "moderation_status",
        "extraction_status",
        "uploader",
        "uploader_history",
        "duplicate_flag",
        "created_at",
    )
    list_filter = (
        "moderation_status",
        "source_type",
        "visibility",
        "extraction_status",
        "license",
    )
    search_fields = ("title", "description", "sha256", "uploader__email")
    readonly_fields = (
        "sha256",
        "storage_key",
        "size_bytes",
        "page_count",
        "download_count",
        "extraction_status",
        "text_preview_admin",
        "created_at",
        "updated_at",
    )
    filter_horizontal = ("oposiciones", "temas")
    autocomplete_fields = ("convocatoria", "canonical_document", "uploader")
    actions = ["approve_documents", "take_down_documents"]
    date_hierarchy = "created_at"

    @admin.display(description="Historial del autor")
    def uploader_history(self, obj: Document) -> str:
        if not obj.uploader_id:
            return "—"
        total = Document.objects.filter(uploader_id=obj.uploader_id).count()
        rejected = Document.objects.filter(
            uploader_id=obj.uploader_id,
            moderation_status=Document.ModerationStatus.REJECTED,
        ).count()
        return f"{total} subidas / {rejected} rechazadas"

    @admin.display(description="Duplicado", boolean=True)
    def duplicate_flag(self, obj: Document) -> bool:
        return obj.canonical_document_id is not None

    @admin.display(description="Vista previa del texto extraído")
    def text_preview_admin(self, obj: Document) -> str:
        preview = obj.extracted_text[:2000] or "(sin texto extraído)"
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", preview)

    @admin.action(description="Aprobar documentos seleccionados")
    def approve_documents(self, request: HttpRequest, queryset: QuerySet) -> None:
        for document in queryset:
            old = document.moderation_status
            if old == Document.ModerationStatus.APPROVED:
                continue
            document.moderation_status = Document.ModerationStatus.APPROVED
            document.save(update_fields=["moderation_status", "updated_at"])
            _log_status_change(document, request.user, old, "approved")
        self.message_user(request, "Documentos aprobados.", messages.SUCCESS)

    @admin.action(description="Retirar documentos seleccionados (takedown)")
    def take_down_documents(self, request: HttpRequest, queryset: QuerySet) -> None:
        from search.backends import get_backend

        for document in queryset:
            old = document.moderation_status
            document.moderation_status = Document.ModerationStatus.TAKEN_DOWN
            document.save(update_fields=["moderation_status", "updated_at"])
            _log_status_change(document, request.user, old, "taken_down", "Takedown")
            get_backend().remove(document)
        self.message_user(request, "Documentos retirados (410).", messages.WARNING)

    def save_model(
        self, request: HttpRequest, obj: Document, form: forms.ModelForm, change: bool
    ) -> None:
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        old_status = None
        if change:
            old_status = (
                Document.objects.filter(pk=obj.pk)
                .values_list("moderation_status", flat=True)
                .first()
            )
        uploaded = form.cleaned_data.get("archivo")
        if uploaded:
            blob = form._blob
            obj.sha256 = form._sha256
            obj.storage_key = Document.storage_key_for(obj.sha256)
            obj.mime_type = uploaded.content_type or obj.mime_type
            obj.size_bytes = len(blob)
            default_storage.save(obj.storage_key, ContentFile(blob))
        super().save_model(request, obj, form, change)
        if change and old_status and old_status != obj.moderation_status:
            _log_status_change(obj, request.user, old_status, obj.moderation_status)
            if (
                obj.moderation_status == Document.ModerationStatus.REJECTED
                and obj.uploader
                and obj.uploader.email
            ):
                send_mail(
                    "Tu documento ha sido rechazado",
                    f'El documento "{obj.title}" no ha superado la revisión.',
                    None,
                    [obj.uploader.email],
                    fail_silently=True,
                )
        if not change:
            # Editorial/official uploads from the admin enter the pipeline too.
            from .tasks import start_pipeline

            if obj.storage_key:
                start_pipeline(obj.pk)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("document", "reason", "status", "reporter", "created_at")
    list_filter = ("reason", "status")
    search_fields = ("document__title", "detail")
    autocomplete_fields = ("document", "reporter")


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    """Immutable: read-only in the admin, writes happen in code only."""

    list_display = ("document", "from_status", "to_status", "actor", "created_at")
    search_fields = ("document__title",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False
