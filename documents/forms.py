from typing import Any

from django import forms

from oposiciones.models import Oposicion

from .models import LICENSE_CHOICES, Document, Report

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class DocumentUploadForm(forms.Form):
    title = forms.CharField(label="Título", max_length=300)
    description = forms.CharField(
        label="Descripción", widget=forms.Textarea(attrs={"rows": 4}), required=False
    )
    oposiciones = forms.ModelMultipleChoiceField(
        label="Oposiciones",
        queryset=Oposicion.objects.filter(is_published=True).order_by("nombre"),
        help_text="Selecciona al menos una oposición.",
    )
    # Explicit licence declaration the user must actively select: no default.
    license = forms.ChoiceField(
        label="Declaración de licencia",
        choices=LICENSE_CHOICES,
        widget=forms.RadioSelect,
        initial=None,
    )
    file = forms.FileField(label="Archivo (PDF o DOCX, máx. 50 MB)")

    def clean_file(self) -> Any:
        uploaded = self.cleaned_data["file"]
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("El archivo supera el tamaño máximo de 50 MB.")
        if uploaded.content_type not in ALLOWED_MIME_TYPES:
            raise forms.ValidationError("Solo se admiten archivos PDF o DOCX.")
        return uploaded


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["document", "reason", "detail", "contact_email"]
        labels = {
            "document": "Documento afectado",
            "reason": "Motivo",
            "detail": "Detalle de la reclamación",
            "contact_email": "Email de contacto",
        }
        widgets = {"detail": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["document"].queryset = Document.objects.exclude(  # type: ignore[attr-defined]
            moderation_status=Document.ModerationStatus.TAKEN_DOWN
        ).order_by("-created_at")
