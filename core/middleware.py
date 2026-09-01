"""Markdown content negotiation.

Appending ``.md`` to any public URL returns a clean markdown rendering of that
page: no navigation chrome, no ads, no boilerplate. The middleware rewrites the
path so normal URL resolution applies and flags the request; views built on
``core.views.MarkdownNegotiationMixin`` then render their markdown template
with ``text/markdown``.
"""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


class MarkdownNegotiationMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.wants_markdown = False  # type: ignore[attr-defined]
        path = request.path_info
        if path.endswith(".md") and not path.startswith(("/static/", "/admin/")):
            stripped = path[: -len(".md")]
            # Both /oposiciones/x.md and /oposiciones/x/.md map to /oposiciones/x/
            if not stripped.endswith("/"):
                stripped += "/"
            if stripped == "/llms/":  # /llms.txt is its own endpoint, leave it alone
                return self.get_response(request)
            request.path_info = stripped
            request.path = stripped
            request.wants_markdown = True  # type: ignore[attr-defined]
        return self.get_response(request)
