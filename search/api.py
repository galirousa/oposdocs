"""Public, read-only, rate-limited JSON search API.

Deliberate: it gives agents and downstream tools a clean way to query the
site — a second discovery channel alongside crawling.
"""

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from .backends import get_backend
from .views import _read_filters

RATE_LIMIT = 60  # requests per minute per client IP


def _rate_limited(request: HttpRequest) -> bool:
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or (
        request.META.get("REMOTE_ADDR", "unknown")
    )
    key = f"api-buscar:{ip}"
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=60)
        count = 1
    return count > RATE_LIMIT


@require_GET
def api_buscar(request: HttpRequest) -> JsonResponse:
    if _rate_limited(request):
        return JsonResponse(
            {"error": "rate_limited", "detail": "Máximo 60 peticiones por minuto."},
            status=429,
        )
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse(
            {"error": "missing_query", "detail": "Parámetro q requerido."}, status=400
        )
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except ValueError:
        page = 1
    result_page = get_backend().query(query, filters=_read_filters(request), page=page)
    site = settings.SITE_URL.rstrip("/")
    return JsonResponse(
        {
            "query": query,
            "total": result_page.total,
            "page": result_page.page,
            "per_page": result_page.per_page,
            "results": [
                {
                    "title": r.document.title,
                    "url": site + r.document.get_absolute_url(),
                    "url_markdown": site + r.document.get_absolute_url().rstrip("/") + ".md",
                    "description": r.document.description,
                    "snippet": r.headline,
                    "source_type": r.document.source_type,
                    "mime_type": r.document.mime_type,
                    "pages": r.document.page_count,
                    "oposiciones": [
                        {"name": op.derived_title, "url": site + op.get_absolute_url()}
                        for op in r.document.oposiciones.all()
                    ],
                }
                for r in result_page.results
            ],
        },
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def api_schema(request: HttpRequest) -> JsonResponse:
    """Hand-authored OpenAPI 3.1 schema for the public search API."""
    site = settings.SITE_URL.rstrip("/")
    schema: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": f"{settings.SITE_NAME} — API de búsqueda",
            "version": "1.0.0",
            "description": (
                "API pública de solo lectura para buscar documentos de "
                "oposiciones. Limitada a 60 peticiones por minuto por IP."
            ),
        },
        "servers": [{"url": site}],
        "paths": {
            "/api/buscar/": {
                "get": {
                    "summary": "Buscar documentos",
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "page",
                            "in": "query",
                            "schema": {"type": "integer", "minimum": 1},
                        },
                        {
                            "name": "ambito",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["estado", "autonomica", "local"]},
                        },
                        {
                            "name": "grupo",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["A1", "A2", "B", "C1", "C2", "E"],
                            },
                        },
                        {
                            "name": "oposicion",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Slug de la oposición",
                        },
                        {
                            "name": "source_type",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["official", "editorial", "user"]},
                        },
                        {"name": "anio", "in": "query", "schema": {"type": "integer"}},
                        {
                            "name": "tipo",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Tipo MIME",
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Resultados de búsqueda",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SearchResponse"}
                                }
                            },
                        },
                        "429": {"description": "Límite de peticiones superado"},
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "SearchResponse": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "total": {"type": "integer"},
                        "page": {"type": "integer"},
                        "per_page": {"type": "integer"},
                        "results": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/SearchResult"},
                        },
                    },
                },
                "SearchResult": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string", "format": "uri"},
                        "url_markdown": {"type": "string", "format": "uri"},
                        "description": {"type": "string"},
                        "snippet": {"type": "string"},
                        "source_type": {"type": "string"},
                        "mime_type": {"type": "string"},
                        "pages": {"type": ["integer", "null"]},
                        "oposiciones": {"type": "array", "items": {"type": "object"}},
                    },
                },
            }
        },
    }
    return JsonResponse(schema, json_dumps_params={"ensure_ascii": False})
