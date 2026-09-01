from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("display_title", "author", "status", "moderation_status", "published_at")
    list_filter = ("status", "moderation_status", "oposiciones")
    search_fields = ("title", "draft_title", "body", "draft_body")
    date_hierarchy = "created_at"
    filter_horizontal = ("oposiciones",)
    readonly_fields = ("created_at", "updated_at", "draft_saved_at", "rendered_preview")
    fieldsets = (
        (None, {"fields": ("author", "status", "moderation_status", "oposiciones")}),
        ("Contenido publicado", {"fields": ("title", "slug", "body", "rendered_preview")}),
        (
            "Borrador en curso",
            {
                "fields": ("draft_title", "draft_body", "draft_saved_at"),
                "description": (
                    "Copia de trabajo del autor. Editarla aquí no cambia lo que ven "
                    "los lectores hasta que el apunte se publica."
                ),
            },
        ),
        ("Fechas", {"fields": ("published_at", "created_at", "updated_at")}),
    )
    actions = ("approve", "flag", "take_down")

    @admin.display(description="título")
    def display_title(self, obj: Post) -> str:
        return obj.display_title

    @admin.display(description="vista renderizada")
    def rendered_preview(self, obj: Post) -> Any:
        return format_html('<div class="post-body">{}</div>', format_html(obj.body_html))

    @admin.action(description="Aprobar los apuntes seleccionados")
    def approve(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(moderation_status=Post.ModerationStatus.APPROVED)

    @admin.action(description="Señalar los apuntes seleccionados")
    def flag(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(moderation_status=Post.ModerationStatus.FLAGGED)

    @admin.action(description="Retirar los apuntes seleccionados (410 Gone)")
    def take_down(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(moderation_status=Post.ModerationStatus.TAKEN_DOWN)
