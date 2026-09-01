from typing import Any

from django import forms

from oposiciones.models import Oposicion

MAX_TITLE_CHARS = 300
# A generous ceiling that still bounds what one autosave can push into the
# database; roughly 15.000 words.
MAX_BODY_CHARS = 100_000

MARKDOWN_HELP = (
    "Puedes dar formato con Markdown: **negrita**, *cursiva*, `código`, "
    "## títulos, - listas, > citas, [enlaces](https://…) y tablas."
)


class PostForm(forms.Form):
    """The editor form.

    It writes to the post's working copy, not to the live fields, so the same
    form serves a new draft and an edit of an already published post.

    Title and body are only *required* when publishing: saving an unfinished
    draft must never be blocked by validation.
    """

    title = forms.CharField(label="Título", max_length=MAX_TITLE_CHARS, required=False)
    body = forms.CharField(
        label="Texto",
        required=False,
        help_text=MARKDOWN_HELP,
        widget=forms.Textarea(attrs={"rows": 22, "class": "editor-body"}),
    )
    oposiciones = forms.ModelMultipleChoiceField(
        label="Oposiciones relacionadas",
        required=False,
        queryset=Oposicion.objects.filter(is_published=True).order_by("nombre"),
        help_text="Opcional. Ayuda a que otras personas encuentren tu apunte.",
    )

    def __init__(self, *args: Any, publishing: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.publishing = publishing
        if publishing:
            self.fields["title"].required = True
            self.fields["body"].required = True

    def clean_body(self) -> str:
        body: str = self.cleaned_data.get("body", "")
        if len(body) > MAX_BODY_CHARS:
            raise forms.ValidationError(
                f"El texto supera el máximo de {MAX_BODY_CHARS:,} caracteres.".replace(",", ".")
            )
        return body
