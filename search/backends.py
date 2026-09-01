"""Search behind a backend abstraction so Meilisearch can be swapped in later
without touching call sites. Select via the SEARCH_BACKEND setting."""

import dataclasses
from typing import TYPE_CHECKING, Protocol

from django.conf import settings

if TYPE_CHECKING:  # pragma: no cover
    from documents.models import Document


@dataclasses.dataclass
class SearchResult:
    document: "Document"
    rank: float
    headline: str


@dataclasses.dataclass
class SearchPage:
    results: list[SearchResult]
    total: int
    page: int
    per_page: int

    @property
    def num_pages(self) -> int:
        return max(1, -(-self.total // self.per_page))

    @property
    def page_range(self) -> range:
        return range(1, self.num_pages + 1)

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.num_pages


class SearchBackend(Protocol):
    def index(self, document: "Document") -> None: ...

    def remove(self, document: "Document") -> None: ...

    def query(
        self, text: str, filters: dict[str, str] | None = None, page: int = 1
    ) -> SearchPage: ...


def get_backend() -> SearchBackend:
    if settings.SEARCH_BACKEND == "postgres":
        from .postgres import PostgresSearchBackend

        return PostgresSearchBackend()
    raise ValueError(f"Unknown SEARCH_BACKEND {settings.SEARCH_BACKEND!r}")
