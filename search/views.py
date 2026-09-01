from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from oposiciones.models import Oposicion

from .backends import get_backend

FILTER_KEYS = ("ambito", "grupo", "oposicion", "source_type", "anio", "tipo")


def _read_filters(request: HttpRequest) -> dict[str, str]:
    return {key: request.GET.get(key, "").strip() for key in FILTER_KEYS if request.GET.get(key)}


def buscar(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "").strip()
    filters = _read_filters(request)
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except ValueError:
        page = 1

    results = None
    if query:
        results = get_backend().query(query, filters=filters, page=page)

    # Empty state suggests popular oposiciones rather than showing nothing.
    suggestions: list[Any] = []
    if not query or (results and results.total == 0):
        suggestions = list(
            Oposicion.objects.filter(is_published=True, is_featured=True).order_by(
                "homepage_order"
            )[:8]
        )

    context = {
        "query": query,
        "results": results,
        "filters": filters,
        "suggestions": suggestions,
        "ambitos": Oposicion.Ambito.choices,
        "grupos": Oposicion.Grupo.choices,
        "oposiciones_facet": Oposicion.objects.filter(is_published=True).order_by("nombre"),
        "meta_title": f'Resultados para "{query}"' if query else "Buscar documentos",
        "meta_description": "Busca documentos, temarios y convocatorias de oposiciones.",
        # Filtered/query result pages are noindex,follow, canonical to /buscar/.
        "noindex": True,
        "canonical_path": "/buscar/",
    }
    return render(request, "search/buscar.html", context)
