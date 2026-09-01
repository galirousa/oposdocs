"""JSON-LD builders.

The visible facts block and the structured data must never diverge, so both
are generated from the same source: the model's ``facts()`` method feeds the
<dl> and the markdown table, and these builders read the same model fields.
"""

from datetime import date
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:  # pragma: no cover
    from documents.models import Document
    from oposiciones.models import Convocatoria, Oposicion
    from posts.models import Post


def absolute(path: str) -> str:
    return settings.SITE_URL.rstrip("/") + path


def organization_jsonld() -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": settings.SITE_NAME,
        "url": absolute("/"),
    }


def website_jsonld() -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": settings.SITE_NAME,
        "url": absolute("/"),
        "inLanguage": "es",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": absolute("/buscar/?q={search_term_string}"),
            },
            "query-input": "required name=search_term_string",
        },
    }


def breadcrumbs_jsonld(crumbs: list[tuple[str, str]]) -> dict[str, Any]:
    """crumbs: list of (name, path)."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": name,
                "item": absolute(path),
            }
            for i, (name, path) in enumerate(crumbs)
        ],
    }


def oposicion_jsonld(oposicion: "Oposicion") -> dict[str, Any]:
    documents = list(
        oposicion.documents.filter(visibility="public", moderation_status="approved").order_by(
            "-created_at"
        )[:50]
    )
    return {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": oposicion.derived_title,
        "url": absolute(oposicion.get_absolute_url()),
        "inLanguage": "es",
        "description": oposicion.answer_paragraph,
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(documents),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "name": doc.title,
                    "url": absolute(doc.get_absolute_url()),
                }
                for i, doc in enumerate(documents)
            ],
        },
    }


def convocatoria_jsonld(convocatoria: "Convocatoria") -> dict[str, Any] | None:
    """JobPosting — these are literally public job openings (Google Jobs).

    Only emitted while the convocatoria is open and the deadline is in the
    future: stale JobPosting markup gets the site penalised.
    """
    if convocatoria.estado != "abierta":
        return None
    limite = convocatoria.fecha_limite_solicitud
    if not limite or limite < date.today():
        return None
    oposicion = convocatoria.oposicion
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": oposicion.derived_title,
        "description": convocatoria.descripcion_jobposting,
        "datePosted": (
            convocatoria.fecha_publicacion.isoformat() if convocatoria.fecha_publicacion else None
        ),
        "validThrough": limite.isoformat(),
        "employmentType": "FULL_TIME",
        "hiringOrganization": {
            "@type": "Organization",
            "name": oposicion.organismo_convocante or "Administración General del Estado",
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressRegion": oposicion.comunidad_display or "España",
                "addressCountry": "ES",
            },
        },
        "url": absolute(convocatoria.get_absolute_url()),
    }
    if convocatoria.plazas:
        payload["totalJobOpenings"] = convocatoria.plazas
    return {k: v for k, v in payload.items() if v is not None}


def document_jsonld(document: "Document") -> dict[str, Any]:
    oposicion = document.oposiciones.first()
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "DigitalDocument",
        "name": document.title,
        "url": absolute(document.get_absolute_url()),
        "inLanguage": "es",
        "description": document.description or None,
        "encodingFormat": document.mime_type or None,
        "isAccessibleForFree": document.visibility == "public",
        "license": document.license_url,
        "datePublished": document.created_at.date().isoformat(),
        "dateModified": document.updated_at.date().isoformat(),
    }
    if oposicion:
        payload["about"] = {
            "@type": "Thing",
            "name": oposicion.derived_title,
            "url": absolute(oposicion.get_absolute_url()),
        }
    return {k: v for k, v in payload.items() if v is not None}


def post_jsonld(post: "Post") -> dict[str, Any]:
    """Article — a post is prose written by a person, not a stored file."""
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.display_title[:110],
        "url": absolute(post.get_absolute_url()),
        "inLanguage": "es",
        "description": post.excerpt[:300] or None,
        "wordCount": post.word_count,
        "author": {"@type": "Person", "name": post.author_display},
        "datePublished": post.published_at.date().isoformat() if post.published_at else None,
        "dateModified": post.updated_at.date().isoformat(),
        "publisher": {"@type": "Organization", "name": settings.SITE_NAME},
    }
    oposicion = post.oposiciones.first()
    if oposicion:
        payload["about"] = {
            "@type": "Thing",
            "name": oposicion.derived_title,
            "url": absolute(oposicion.get_absolute_url()),
        }
    return {k: v for k, v in payload.items() if v is not None}
