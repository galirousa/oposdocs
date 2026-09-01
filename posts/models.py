"""Posts (*apuntes*): study notes written directly on the site in markdown.

Like ``Document``, a post keeps the author's intent and the staff's decision on
separate axes — never collapse them:

- ``status``: the AUTHOR's intent, draft or published.
- ``moderation_status``: the STAFF's decision, approved / flagged / taken down.

A post also carries a **working copy** (``draft_title``, ``draft_body``). The
editor always writes to the working copy, and only ``publish()`` copies it over
the live fields. That is what makes autosave safe: autosaving a published post
can never change what readers see, and autosaving a new post produces a draft
and nothing else.
"""

from typing import Any

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from oposiciones.models import Oposicion

from .rendering import render_markdown, strip_html

# Literal segments under /apuntes/ that a slug must never shadow.
RESERVED_SLUGS = {"nuevo", "mis-apuntes", "autoguardar", "editar", "publicar", "eliminar"}

# Below this much prose a post is thin content: published, but not indexable.
MIN_INDEXABLE_CHARS = 200

WORDS_PER_MINUTE = 200


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PUBLISHED = "published", "Publicado"

    class ModerationStatus(models.TextChoices):
        APPROVED = "approved", "Aprobado"
        FLAGGED = "flagged", "Señalado"
        TAKEN_DOWN = "taken_down", "Retirado"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
        verbose_name="autor",
    )
    # --- Live fields: what the public sees ---------------------------------
    title = models.CharField("título", max_length=300, blank=True)
    slug = models.SlugField("slug", max_length=320, unique=True, blank=True)
    body = models.TextField("texto (markdown)", blank=True)
    body_html = models.TextField("texto renderizado", blank=True, editable=False)
    # --- Working copy: what the editor writes to ---------------------------
    draft_title = models.CharField("título del borrador", max_length=300, blank=True)
    draft_body = models.TextField("texto del borrador (markdown)", blank=True)
    draft_saved_at = models.DateTimeField("último autoguardado", null=True, blank=True)
    # --- The two axes ------------------------------------------------------
    status = models.CharField("estado", max_length=10, choices=Status.choices, default=Status.DRAFT)
    moderation_status = models.CharField(
        "estado de moderación",
        max_length=10,
        choices=ModerationStatus.choices,
        default=ModerationStatus.APPROVED,
    )
    oposiciones = models.ManyToManyField(
        Oposicion, blank=True, related_name="posts", verbose_name="oposiciones"
    )
    created_at = models.DateTimeField("fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("última modificación", auto_now=True)
    published_at = models.DateTimeField("fecha de publicación", null=True, blank=True)

    class Meta:
        verbose_name = "apunte"
        verbose_name_plural = "apuntes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "moderation_status"], name="post_status_idx"),
        ]

    def __str__(self) -> str:
        return self.display_title

    # --- Titles and slugs ---------------------------------------------------

    @property
    def display_title(self) -> str:
        return self.title or self.draft_title or "Apunte sin título"

    def _build_slug(self) -> str:
        base = slugify(self.display_title)[:280] or "apunte"
        if base in RESERVED_SLUGS:
            base = f"{base}-apunte"
        slug = base
        n = 2
        while Post.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        return slug

    def save(self, *args: Any, **kwargs: Any) -> None:
        update_fields = kwargs.get("update_fields")
        # An autosave writes only working-copy fields; it must not touch the
        # live slug or the rendered HTML.
        touches_live = update_fields is None or bool(
            {"title", "body", "slug", "status"} & set(update_fields)
        )
        if touches_live:
            # Slugs are immutable once published (CLAUDE.md): a draft's slug
            # follows its title, a published post's slug is frozen.
            if not self.slug or self.published_at is None:
                self.slug = self._build_slug()
            self.body_html = render_markdown(self.body)
            if update_fields is not None:
                kwargs["update_fields"] = list(set(update_fields) | {"slug", "body_html"})
        super().save(*args, **kwargs)

    # --- Working copy -------------------------------------------------------

    @property
    def has_working_copy(self) -> bool:
        return self.draft_saved_at is not None

    @property
    def editor_title(self) -> str:
        """What the editor form should show — the working copy wins."""
        return self.draft_title if self.has_working_copy else self.title

    @property
    def editor_body(self) -> str:
        return self.draft_body if self.has_working_copy else self.body

    @property
    def has_unpublished_changes(self) -> bool:
        return self.has_working_copy and (
            self.draft_title != self.title or self.draft_body != self.body
        )

    def save_draft(self, title: str, body: str) -> None:
        """Store the working copy. Never touches the live fields."""
        self.draft_title = title[:300]
        self.draft_body = body
        self.draft_saved_at = timezone.now()
        self.save(update_fields=["draft_title", "draft_body", "draft_saved_at", "updated_at"])

    def publish(self) -> None:
        """Promote the working copy to the live fields and go public."""
        if self.has_working_copy:
            self.title = self.draft_title
            self.body = self.draft_body
        self.status = self.Status.PUBLISHED
        if self.published_at is None:
            self.published_at = timezone.now()
            # First publication fixes the URL; save() will not rebuild it again.
            self.slug = self._build_slug()
        self.save()

    def unpublish(self) -> None:
        """Back to draft. ``published_at`` is kept on purpose: the URL was
        public once, so the slug stays frozen if the post returns."""
        self.status = self.Status.DRAFT
        self.save(update_fields=["status", "updated_at"])

    # --- Derived content ----------------------------------------------------

    @property
    def plain_text(self) -> str:
        return strip_html(self.body_html)

    @property
    def excerpt(self) -> str:
        words = self.plain_text.split()
        preview = " ".join(words[:45])
        return f"{preview} …" if len(words) > 45 else preview

    @property
    def word_count(self) -> int:
        return len(self.plain_text.split())

    @property
    def reading_time(self) -> int:
        return max(1, round(self.word_count / WORDS_PER_MINUTE))

    @property
    def author_display(self) -> str:
        """Never the email address: that is login data, not a byline."""
        if not self.author:
            return "Autor eliminado"
        return self.author.get_full_name() or self.author.get_username()

    # --- Visibility ---------------------------------------------------------

    @property
    def is_publicly_visible(self) -> bool:
        return (
            self.status == self.Status.PUBLISHED
            and self.moderation_status == self.ModerationStatus.APPROVED
        )

    @property
    def is_thin(self) -> bool:
        return len(self.plain_text) < MIN_INDEXABLE_CHARS

    @property
    def is_indexable(self) -> bool:
        return self.is_publicly_visible and not self.is_thin

    def can_edit(self, user: Any) -> bool:
        return bool(
            user.is_authenticated and self.author_id is not None and self.author_id == user.pk
        )

    def can_view(self, user: Any) -> bool:
        """Drafts, flagged and taken-down posts are author/staff only."""
        if self.is_publicly_visible:
            return True
        if getattr(user, "is_staff", False):
            return True
        return self.can_edit(user)

    def facts(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = [("Autor", self.author_display)]
        if self.published_at:
            rows.append(("Publicado", self.published_at.strftime("%d/%m/%Y")))
        rows.append(("Actualizado", self.updated_at.strftime("%d/%m/%Y")))
        rows.append(("Tiempo de lectura", f"{self.reading_time} min"))
        first = self.oposiciones.first()
        if first:
            rows.append(("Oposición", first.derived_title))
        return rows

    def get_absolute_url(self) -> str:
        return reverse("posts:detail", kwargs={"slug": self.slug})
