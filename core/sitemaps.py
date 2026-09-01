"""Sitemap index with separate sitemaps per section, lastmod from updated_at.

Search engines discover the sitemap via the Sitemap: line in robots.txt; the
old ping endpoints were retired by Google in 2023, so there is nothing to ping
on publish any more.
"""

from datetime import datetime

from django.contrib.sitemaps import Sitemap
from django.db.models import QuerySet


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self) -> list[str]:
        return ["/", "/oposiciones/", "/apuntes/", "/aviso-legal/", "/retirada-de-contenido/"]

    def location(self, item: str) -> str:
        return item


class OposicionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self) -> QuerySet:
        from oposiciones.models import Oposicion

        return Oposicion.objects.filter(is_published=True).order_by("slug")

    def lastmod(self, obj: object) -> datetime:
        return obj.updated_at  # type: ignore[attr-defined]


class ConvocatoriaSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self) -> QuerySet:
        from oposiciones.models import Convocatoria

        return Convocatoria.objects.filter(oposicion__is_published=True).order_by("slug")

    def lastmod(self, obj: object) -> datetime:
        return obj.updated_at  # type: ignore[attr-defined]


class DocumentSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self) -> QuerySet:
        from documents.models import Document

        # Only approved public documents that carry indexable content: pending
        # and taken-down documents are excluded entirely, as are thin pages.
        return (
            Document.objects.filter(
                visibility=Document.Visibility.PUBLIC,
                moderation_status=Document.ModerationStatus.APPROVED,
                canonical_document__isnull=True,
            )
            .exclude(description="", extracted_text="")
            .order_by("slug")
        )

    def lastmod(self, obj: object) -> datetime:
        return obj.updated_at  # type: ignore[attr-defined]


class PostSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self) -> list:
        from posts.models import Post

        # Drafts and flagged/taken-down posts never reach the sitemap; thin
        # posts are filtered in Python because the guard reads rendered text.
        published = Post.objects.filter(
            status=Post.Status.PUBLISHED,
            moderation_status=Post.ModerationStatus.APPROVED,
        ).order_by("slug")
        return [post for post in published if post.is_indexable]

    def lastmod(self, obj: object) -> datetime:
        return obj.updated_at  # type: ignore[attr-defined]


SITEMAPS = {
    "estaticas": StaticSitemap,
    "oposiciones": OposicionSitemap,
    "convocatorias": ConvocatoriaSitemap,
    "documentos": DocumentSitemap,
    "apuntes": PostSitemap,
}
