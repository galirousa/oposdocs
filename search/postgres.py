"""PostgreSQL full-text search backend.

The heavy lifting lives in the database: ``search_vector`` is a weighted
generated column over title (A), tema/oposición names (B), description (C)
and extracted text (D), using the 'es_unaccent' configuration so accented and
unaccented queries return identical results.
"""

from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db.models import F, QuerySet

from documents.models import Document

from .backends import SearchPage, SearchResult

CONFIG = "es_unaccent"
PER_PAGE = 20


class PostgresSearchBackend:
    def index(self, document: Document) -> None:
        # The vector itself is a generated column; indexing means refreshing
        # the denormalised weight-B tags so the next write picks them up.
        tags = [op.derived_title for op in document.oposiciones.all()]
        tags += [tema.titulo for tema in document.temas.all()]
        tags_text = " ".join(tags)
        if tags_text != document.tags_text:
            document.tags_text = tags_text
        document.save(update_fields=["tags_text", "updated_at"])

    def remove(self, document: Document) -> None:
        # Postgres search reads live rows, so removal is handled by the
        # queryset filters below (moderation/visibility). Nothing to delete.
        return

    def _base_queryset(self) -> QuerySet:
        return Document.objects.filter(
            visibility=Document.Visibility.PUBLIC,
            moderation_status=Document.ModerationStatus.APPROVED,
        ).prefetch_related("oposiciones")

    def query(self, text: str, filters: dict[str, str] | None = None, page: int = 1) -> SearchPage:
        filters = filters or {}
        search_query = SearchQuery(text, config=CONFIG, search_type="websearch")
        qs = (
            self._base_queryset()
            .filter(search_vector=search_query)
            .annotate(
                rank=SearchRank(F("search_vector"), search_query),
                headline=SearchHeadline(
                    "extracted_text",
                    search_query,
                    config=CONFIG,
                    max_words=40,
                    min_words=20,
                    start_sel="<mark>",
                    stop_sel="</mark>",
                ),
            )
        )
        if filters.get("ambito"):
            qs = qs.filter(oposiciones__ambito=filters["ambito"])
        if filters.get("grupo"):
            qs = qs.filter(oposiciones__grupo=filters["grupo"])
        if filters.get("oposicion"):
            qs = qs.filter(oposiciones__slug=filters["oposicion"])
        if filters.get("source_type"):
            qs = qs.filter(source_type=filters["source_type"])
        if filters.get("anio"):
            qs = qs.filter(convocatoria__anio=filters["anio"])
        if filters.get("tipo"):
            qs = qs.filter(mime_type=filters["tipo"])
        qs = qs.distinct().order_by("-rank", "-created_at")
        total = qs.count()
        offset = (page - 1) * PER_PAGE
        results = [
            SearchResult(document=doc, rank=doc.rank, headline=doc.headline or "")
            for doc in qs[offset : offset + PER_PAGE]
        ]
        return SearchPage(results=results, total=total, page=page, per_page=PER_PAGE)
