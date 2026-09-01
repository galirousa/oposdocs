import hashlib
import json
from typing import Any

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView


def healthz(request: HttpRequest) -> JsonResponse:
    """Health check polled by external uptime monitoring: DB + Redis."""
    checks: dict[str, str] = {}
    healthy = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        healthy = False

    try:
        from django.core.cache import cache

        cache.set("healthz", "ok", 10)
        checks["redis"] = "ok" if cache.get("healthz") == "ok" else "error: readback failed"
        healthy = healthy and checks["redis"] == "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        healthy = False

    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )


# AI crawlers are welcome: being cited by an assistant is distribution, and
# this is a discovery product. Crawl-delay paces the aggressive ones because
# upstream bandwidth (home fibre) is limited.
_ALLOWED_BOTS = [
    "Googlebot",
    "Bingbot",
    "Google-Extended",
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-User",
    "Claude-SearchBot",
    "PerplexityBot",
    "Perplexity-User",
    "CCBot",
    "Applebot",
    "Applebot-Extended",
]
_THROTTLED_BOTS = ["GPTBot", "CCBot", "ClaudeBot", "PerplexityBot", "Applebot-Extended"]
_DISALLOWED_PATHS = ["/admin/", "/api/internal/", "/cuentas/"]
# Filter query parameters are crawl traps; plain pagination (?page=) stays crawlable.
_FILTER_PARAMS = ["ambito=", "grupo=", "oposicion=", "source_type=", "anio=", "tipo="]


def robots_txt(request: HttpRequest) -> HttpResponse:
    """Environment-aware robots.txt (staging disallows everything)."""
    lines: list[str] = [
        "# NOTE FOR OPERATORS: Cloudflare's 'Block AI Scrapers and Crawlers'",
        "# setting (Security -> Bots) must be OFF in the dashboard, or this",
        "# file is overridden at the edge and none of it takes effect.",
        "",
    ]
    if not settings.ALLOW_INDEXING:
        lines += ["User-agent: *", "Disallow: /", ""]
    else:
        for bot in _ALLOWED_BOTS:
            lines += [f"User-agent: {bot}", "Allow: /"]
            for path in _DISALLOWED_PATHS:
                lines.append(f"Disallow: {path}")
            for param in _FILTER_PARAMS:
                lines.append(f"Disallow: /*?*{param}")
            if bot in _THROTTLED_BOTS:
                lines.append("Crawl-delay: 5")
            lines.append("")
        lines += ["User-agent: *", "Allow: /"]
        for path in _DISALLOWED_PATHS:
            lines.append(f"Disallow: {path}")
        for param in _FILTER_PARAMS:
            lines.append(f"Disallow: /*?*{param}")
        lines.append("")
        lines.append(f"Sitemap: {settings.SITE_URL.rstrip('/')}/sitemap.xml")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


@cache_page(60 * 60)
def llms_txt(request: HttpRequest) -> HttpResponse:
    """llms.txt: a markdown map of the site for language-model agents."""
    from oposiciones.models import Oposicion

    site = settings.SITE_URL.rstrip("/")
    lines = [
        f"# {settings.SITE_NAME}",
        "",
        "> Plataforma de documentos para preparar oposiciones en España:",
        "> documentos oficiales (BOE, convocatorias, bases), materiales",
        "> editoriales y apuntes aportados por usuarios. Contenido en español.",
        "",
        "Cada URL pública admite el sufijo `.md` y devuelve la misma página en",
        "markdown limpio, sin navegación ni publicidad. También hay una API de",
        f"búsqueda JSON de solo lectura documentada en {site}/api/schema/.",
        "",
        "## Secciones principales",
        "",
        f"- [Índice de oposiciones]({site}/oposiciones/)",
        f"- [Apuntes escritos por la comunidad]({site}/apuntes/)",
        f"- [Búsqueda]({site}/buscar/?q=...)",
        f"- [Mapa del sitio]({site}/sitemap.xml)",
        "",
        "## Oposiciones publicadas",
        "",
    ]
    for op in Oposicion.objects.filter(is_published=True).order_by("nombre"):
        lines.append(f"- [{op.derived_title}]({site}{op.get_absolute_url()})")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/markdown; charset=utf-8")


def aviso_legal(request: HttpRequest) -> HttpResponse:
    return render(request, "core/aviso_legal.html", {"hide_ads": True})


def privacidad(request: HttpRequest) -> HttpResponse:
    return render(request, "core/privacidad.html", {"hide_ads": True})


def retirada_de_contenido(request: HttpRequest) -> HttpResponse:
    """Notice-and-takedown page + form (LSSI safe-harbour requirement)."""
    from documents.forms import ReportForm

    submitted = False
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            if request.user.is_authenticated:
                report.reporter = request.user
            report.save()
            submitted = True
            form = ReportForm()
    else:
        form = ReportForm()
    return render(
        request,
        "core/retirada_de_contenido.html",
        {"form": form, "submitted": submitted, "hide_ads": True},
    )


@require_POST
def log_consent(request: HttpRequest) -> JsonResponse:
    """Server-side audit log of consent events; state itself lives client-side."""
    from core.models import ConsentEvent

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False}, status=400)
    decision = payload.get("decision")
    if decision not in dict(ConsentEvent.Decision.choices):
        return JsonResponse({"ok": False}, status=400)
    ua_hash = hashlib.sha256(
        request.headers.get("User-Agent", "").encode("utf-8", "replace")
    ).hexdigest()
    ConsentEvent.objects.create(decision=decision, user_agent_hash=ua_hash)
    return JsonResponse({"ok": True})


class MarkdownNegotiationMixin:
    """Render ``markdown_template`` with text/markdown when the URL had .md."""

    markdown_template: str | None = None

    def render_to_response(self, context: dict[str, Any], **response_kwargs: Any) -> HttpResponse:
        request: HttpRequest = self.request  # type: ignore[attr-defined]
        if getattr(request, "wants_markdown", False) and self.markdown_template:
            response = TemplateResponse(
                request,
                self.markdown_template,
                context,
                content_type="text/markdown; charset=utf-8",
            )
            return response
        return super().render_to_response(context, **response_kwargs)  # type: ignore[misc]


__all__ = [
    "DetailView",
    "ListView",
    "MarkdownNegotiationMixin",
    "TemplateView",
    "aviso_legal",
    "healthz",
    "llms_txt",
    "log_consent",
    "privacidad",
    "retirada_de_contenido",
    "robots_txt",
]
