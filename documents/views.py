from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import F, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.generic import DetailView

from core import seo
from core.views import MarkdownNegotiationMixin

from .forms import ALLOWED_MIME_TYPES, DocumentUploadForm
from .ingest import store_document
from .models import Document
from .permissions import can_access
from .storage_utils import presigned_get_url


class DocumentDetailView(MarkdownNegotiationMixin, DetailView):
    template_name = "documents/document_detail.html"
    markdown_template = "documents/document_detail.md"
    context_object_name = "document"

    def get_object(self, queryset: QuerySet | None = None) -> Document:
        try:
            return Document.objects.prefetch_related("oposiciones").get(slug=self.kwargs["slug"])
        except Document.DoesNotExist as exc:
            raise Http404("Documento no encontrado") from exc

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        document: Document = self.object
        # Taken-down documents are 410 Gone, not 404: the URL existed and was
        # removed deliberately, and crawlers deindex 410 faster.
        if document.moderation_status == Document.ModerationStatus.TAKEN_DOWN:
            return HttpResponse(
                "Este documento ha sido retirado.", status=410, content_type="text/plain"
            )
        if not can_access(request.user, document):
            if not request.user.is_authenticated:
                return redirect(f"/cuentas/login/?next={request.path}")
            raise Http404("Documento no disponible")
        context = self.get_context_data(object=document)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        document: Document = context["document"]
        canonical = document.canonical_document or document
        crumbs = [("Inicio", "/"), ("Documentos", "/oposiciones/")]
        first_op = document.oposiciones.first()
        if first_op:
            crumbs.append((first_op.derived_title, first_op.get_absolute_url()))
        crumbs.append((document.title, document.get_absolute_url()))
        context.update(
            {
                "facts": document.facts(),
                # Thin content guard, driven by the model property.
                "noindex": not document.is_indexable,
                "canonical_path": canonical.get_absolute_url(),
                "meta_title": f"{document.title} — documento para oposiciones",
                "meta_description": (document.description or document.text_preview)[:300],
                "jsonld_payloads": [
                    seo.document_jsonld(document),
                    seo.breadcrumbs_jsonld(crumbs),
                ],
            }
        )
        return context


def download_document(request: HttpRequest, slug: str) -> HttpResponse:
    try:
        document = Document.objects.get(slug=slug)
    except Document.DoesNotExist as exc:
        raise Http404("Documento no encontrado") from exc
    if document.moderation_status == Document.ModerationStatus.TAKEN_DOWN:
        return HttpResponse("Retirado.", status=410, content_type="text/plain")
    if not can_access(request.user, document):
        if not request.user.is_authenticated:
            return redirect(f"/cuentas/login/?next={request.path}")
        raise Http404("Documento no disponible")
    if not document.storage_key:
        raise Http404("Este documento no tiene archivo asociado")
    Document.objects.filter(pk=document.pk).update(download_count=F("download_count") + 1)
    # Presigned URL generated per request AFTER the permission check. Never
    # cacheable at the edge.
    url = presigned_get_url(document.storage_key)
    response = HttpResponseRedirect(url)
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def upload_document(request: HttpRequest) -> HttpResponse:
    """User/editorial upload.

    Demo note: the file passes through the app server here; the production
    plan is a presigned direct-to-storage upload from the browser (see
    storage_utils.presigned_put_url) so the server never handles the bytes.
    """
    uploaded_doc: Document | None = None
    duplicate = False
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            is_privileged = (
                request.user.is_staff
                or request.user.groups.filter(name__in=["Contributor", "Editor"]).exists()
            )
            # Dedupe, storage and the pipeline all live in documents.ingest, so
            # the upload view, the admin and the harvester cannot drift apart.
            uploaded_doc, created = store_document(
                upload.read(),
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                uploader=request.user,
                source_type=(
                    Document.SourceType.EDITORIAL
                    if request.user.is_staff
                    else Document.SourceType.USER
                ),
                visibility=Document.Visibility.PUBLIC,
                # Contributors and editors skip the moderation queue.
                moderation_status=(
                    Document.ModerationStatus.APPROVED
                    if is_privileged
                    else Document.ModerationStatus.PENDING
                ),
                mime_type=upload.content_type,
                license=form.cleaned_data["license"],
                oposiciones=form.cleaned_data["oposiciones"],
            )
            duplicate = not created
    else:
        form = DocumentUploadForm()
    return render(
        request,
        "documents/upload.html",
        {
            "form": form,
            "uploaded_doc": uploaded_doc,
            "duplicate": duplicate,
            "allowed_types": ", ".join(ALLOWED_MIME_TYPES.values()),
            "noindex": True,
        },
    )
