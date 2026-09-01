from typing import Any

from django.db.models import QuerySet
from django.http import Http404
from django.views.generic import DetailView, ListView, TemplateView

from core import seo
from core.views import MarkdownNegotiationMixin

from .models import Convocatoria, Oposicion


class HomeView(MarkdownNegotiationMixin, TemplateView):
    template_name = "oposiciones/home.html"
    markdown_template = "oposiciones/home.md"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        featured = Oposicion.objects.filter(is_published=True, is_featured=True).order_by(
            "homepage_order", "nombre"
        )
        abiertas = (
            Convocatoria.objects.filter(
                estado=Convocatoria.Estado.ABIERTA, oposicion__is_published=True
            )
            .select_related("oposicion")
            .order_by("fecha_limite_solicitud")[:10]
        )
        context.update(
            {
                "featured": featured,
                "convocatorias_abiertas": abiertas,
                "meta_title": "Oposiciones en España: temarios, convocatorias y documentos",
                "meta_description": (
                    "Busca y descarga documentos para preparar oposiciones: "
                    "convocatorias oficiales del BOE, temarios y apuntes."
                ),
                "jsonld_payloads": [seo.organization_jsonld(), seo.website_jsonld()],
            }
        )
        return context


class OposicionIndexView(MarkdownNegotiationMixin, ListView):
    template_name = "oposiciones/index.html"
    markdown_template = "oposiciones/index.md"
    context_object_name = "oposiciones"
    paginate_by = 30

    def get_queryset(self) -> QuerySet:
        qs = Oposicion.objects.filter(is_published=True).order_by("nombre")
        ambito = self.request.GET.get("ambito")
        grupo = self.request.GET.get("grupo")
        if ambito in dict(Oposicion.Ambito.choices):
            qs = qs.filter(ambito=ambito)
        if grupo in dict(Oposicion.Grupo.choices):
            qs = qs.filter(grupo=grupo)
        return qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        # Faceted filter combinations canonicalise to the unfiltered page and
        # are noindex,follow; only the clean index is indexable.
        filtered = bool(self.request.GET.get("ambito") or self.request.GET.get("grupo"))
        context.update(
            {
                "is_filtered": filtered,
                "noindex": filtered,
                "canonical_path": "/oposiciones/",
                "ambitos": Oposicion.Ambito.choices,
                "grupos": Oposicion.Grupo.choices,
                "meta_title": "Índice de oposiciones",
                "meta_description": (
                    "Todas las oposiciones con temario, convocatorias y "
                    "documentos: estatales, autonómicas y locales."
                ),
                "jsonld_payloads": [
                    seo.breadcrumbs_jsonld([("Inicio", "/"), ("Oposiciones", "/oposiciones/")])
                ],
            }
        )
        return context


class OposicionMixin:
    """Shared lookup for all oposición subpages."""

    def get_object(self, queryset: QuerySet | None = None) -> Oposicion:
        try:
            return Oposicion.objects.prefetch_related("temas", "convocatorias").get(
                ambito=self.kwargs["ambito"],  # type: ignore[attr-defined]
                slug=self.kwargs["slug"],  # type: ignore[attr-defined]
                is_published=True,
            )
        except Oposicion.DoesNotExist as exc:
            raise Http404("Oposición no encontrada") from exc


class OposicionDetailView(OposicionMixin, MarkdownNegotiationMixin, DetailView):
    template_name = "oposiciones/oposicion_detail.html"
    markdown_template = "oposiciones/oposicion_detail.md"
    context_object_name = "oposicion"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        op: Oposicion = context["oposicion"]
        documents = op.documents.filter(visibility="public", moderation_status="approved").order_by(
            "-created_at"
        )[:25]
        crumbs = [
            ("Inicio", "/"),
            ("Oposiciones", "/oposiciones/"),
            (op.derived_title, op.get_absolute_url()),
        ]
        context.update(
            {
                "documents": documents,
                "facts": op.facts(),
                "meta_title": f"Oposición {op.derived_title}: temario, convocatorias y documentos",
                "meta_description": op.answer_paragraph[:300],
                "canonical_path": op.get_absolute_url(),
                "jsonld_payloads": [
                    seo.oposicion_jsonld(op),
                    seo.breadcrumbs_jsonld(crumbs),
                ],
            }
        )
        return context


class TemarioView(OposicionMixin, MarkdownNegotiationMixin, DetailView):
    template_name = "oposiciones/temario.html"
    markdown_template = "oposiciones/temario.md"
    context_object_name = "oposicion"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        op: Oposicion = context["oposicion"]
        temas = op.temas.all()
        bloques: dict[str, list] = {}
        for tema in temas:
            bloques.setdefault(tema.bloque or "", []).append(tema)
        context.update(
            {
                "bloques": bloques,
                "total_temas": temas.count(),
                "meta_title": f"Temario de {op.derived_title} ({temas.count()} temas)",
                "meta_description": (
                    f"Temario oficial completo de la oposición a {op.derived_title}: "
                    f"{temas.count()} temas."
                ),
                "canonical_path": f"{op.get_absolute_url()}temario/",
                "jsonld_payloads": [
                    seo.breadcrumbs_jsonld(
                        [
                            ("Inicio", "/"),
                            ("Oposiciones", "/oposiciones/"),
                            (op.derived_title, op.get_absolute_url()),
                            ("Temario", f"{op.get_absolute_url()}temario/"),
                        ]
                    )
                ],
            }
        )
        return context


class ConvocatoriaListView(OposicionMixin, MarkdownNegotiationMixin, DetailView):
    template_name = "oposiciones/convocatoria_list.html"
    markdown_template = "oposiciones/convocatoria_list.md"
    context_object_name = "oposicion"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        op: Oposicion = context["oposicion"]
        context.update(
            {
                "convocatorias": op.convocatorias.all(),
                "meta_title": f"Convocatorias de {op.derived_title}",
                "meta_description": (
                    f"Histórico de convocatorias de la oposición a {op.derived_title}: "
                    "plazas, plazos y referencias del BOE."
                ),
                "canonical_path": f"{op.get_absolute_url()}convocatorias/",
                "jsonld_payloads": [
                    seo.breadcrumbs_jsonld(
                        [
                            ("Inicio", "/"),
                            ("Oposiciones", "/oposiciones/"),
                            (op.derived_title, op.get_absolute_url()),
                            ("Convocatorias", f"{op.get_absolute_url()}convocatorias/"),
                        ]
                    )
                ],
            }
        )
        return context


class ConvocatoriaDetailView(MarkdownNegotiationMixin, DetailView):
    template_name = "oposiciones/convocatoria_detail.html"
    markdown_template = "oposiciones/convocatoria_detail.md"
    context_object_name = "convocatoria"

    def get_object(self, queryset: QuerySet | None = None) -> Convocatoria:
        try:
            return Convocatoria.objects.select_related("oposicion").get(
                anio=self.kwargs["anio"],
                slug=self.kwargs["slug"],
                oposicion__is_published=True,
            )
        except Convocatoria.DoesNotExist as exc:
            raise Http404("Convocatoria no encontrada") from exc

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        conv: Convocatoria = context["convocatoria"]
        op = conv.oposicion
        payloads = [
            seo.breadcrumbs_jsonld(
                [
                    ("Inicio", "/"),
                    (op.derived_title, op.get_absolute_url()),
                    (f"Convocatoria {conv.anio}", conv.get_absolute_url()),
                ]
            )
        ]
        job = seo.convocatoria_jsonld(conv)
        if job:
            payloads.append(job)
        context.update(
            {
                "oposicion": op,
                "facts": conv.facts(),
                "meta_title": (f"Convocatoria {conv.anio} de {op.derived_title}: plazas y plazos"),
                "meta_description": conv.descripcion_jobposting[:300],
                "canonical_path": conv.get_absolute_url(),
                "jsonld_payloads": payloads,
            }
        )
        return context
