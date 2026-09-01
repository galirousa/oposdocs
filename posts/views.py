import json
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from core import seo
from core.views import MarkdownNegotiationMixin

from .forms import MAX_BODY_CHARS, MAX_TITLE_CHARS, PostForm
from .models import Post


class PostListView(MarkdownNegotiationMixin, ListView):
    """Public index of published apuntes."""

    template_name = "posts/post_list.html"
    markdown_template = "posts/post_list.md"
    context_object_name = "posts"
    paginate_by = 20

    def get_queryset(self) -> QuerySet:
        return (
            Post.objects.filter(
                status=Post.Status.PUBLISHED,
                moderation_status=Post.ModerationStatus.APPROVED,
            )
            .select_related("author")
            .prefetch_related("oposiciones")
            .order_by("-published_at")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "meta_title": "Apuntes de oposiciones escritos por la comunidad",
                "meta_description": (
                    "Apuntes, resúmenes y esquemas para preparar oposiciones, "
                    "escritos y compartidos por otras personas opositoras."
                ),
                "canonical_path": "/apuntes/",
                "jsonld_payloads": [
                    seo.breadcrumbs_jsonld([("Inicio", "/"), ("Apuntes", "/apuntes/")])
                ],
            }
        )
        return context


class PostDetailView(MarkdownNegotiationMixin, DetailView):
    template_name = "posts/post_detail.html"
    markdown_template = "posts/post_detail.md"
    context_object_name = "post"

    def get_object(self, queryset: QuerySet | None = None) -> Post:
        try:
            return (
                Post.objects.select_related("author")
                .prefetch_related("oposiciones")
                .get(slug=self.kwargs["slug"])
            )
        except Post.DoesNotExist as exc:
            raise Http404("Apunte no encontrado") from exc

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = post = self.get_object()
        # Same rule as documents: a withdrawn URL is 410 Gone, not 404, because
        # crawlers deindex 410 faster.
        if post.moderation_status == Post.ModerationStatus.TAKEN_DOWN and not (
            request.user.is_staff or post.can_edit(request.user)
        ):
            return HttpResponse(
                "Este apunte ha sido retirado.", status=410, content_type="text/plain"
            )
        if not post.can_view(request.user):
            if not request.user.is_authenticated:
                return redirect(f"/cuentas/login/?next={request.path}")
            raise Http404("Apunte no disponible")
        return self.render_to_response(self.get_context_data(object=post))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        post: Post = context["post"]
        crumbs = [
            ("Inicio", "/"),
            ("Apuntes", "/apuntes/"),
            (post.display_title, post.get_absolute_url()),
        ]
        context.update(
            {
                "facts": post.facts(),
                "can_edit": post.can_edit(self.request.user),
                # Drafts and thin posts stay out of the index.
                "noindex": not post.is_indexable,
                "canonical_path": post.get_absolute_url(),
                "meta_title": post.display_title,
                "meta_description": post.excerpt[:300],
                "jsonld_payloads": (
                    [seo.post_jsonld(post), seo.breadcrumbs_jsonld(crumbs)]
                    if post.is_indexable
                    else []
                ),
            }
        )
        return context


# --- Editing ---------------------------------------------------------------


def _editor_context(request: HttpRequest, form: PostForm, post: Post | None) -> dict[str, Any]:
    return {
        "form": form,
        "post": post,
        "max_body_chars": MAX_BODY_CHARS,
        "autosave_url": "/apuntes/autoguardar/",
        # The editor is a private working surface: never indexable.
        "noindex": True,
        "hide_ads": True,
    }


def _apply_form(request: HttpRequest, post: Post, form: PostForm) -> HttpResponse:
    """Store the working copy, then publish or stay a draft."""
    post.save_draft(form.cleaned_data["title"], form.cleaned_data["body"])
    post.oposiciones.set(form.cleaned_data["oposiciones"])
    if form.publishing:
        post.publish()
        messages.success(request, "Apunte publicado.")
        return redirect(post.get_absolute_url())
    messages.success(request, "Borrador guardado.")
    return redirect("posts:edit", pk=post.pk)


@login_required
def post_create(request: HttpRequest) -> HttpResponse:
    """New post.

    A hidden ``post_id`` may already be present: autosave creates the draft
    row as soon as there is something to save, so a manual save afterwards
    must update that draft instead of creating a second one.
    """
    post: Post | None = None
    if request.method == "POST":
        existing_id = request.POST.get("post_id") or ""
        if existing_id.isdigit():
            post = Post.objects.filter(pk=int(existing_id), author=request.user).first()
        form = PostForm(request.POST, publishing=request.POST.get("action") == "publish")
        if form.is_valid():
            if post is None:
                post = Post(author=request.user, status=Post.Status.DRAFT)
                post.draft_title = form.cleaned_data["title"]
                post.save()
            return _apply_form(request, post, form)
    else:
        form = PostForm()
    return render(request, "posts/post_form.html", _editor_context(request, form, post))


@login_required
def post_edit(request: HttpRequest, pk: int) -> HttpResponse:
    post = get_object_or_404(Post, pk=pk, author=request.user)
    if request.method == "POST":
        form = PostForm(request.POST, publishing=request.POST.get("action") == "publish")
        if form.is_valid():
            return _apply_form(request, post, form)
    else:
        form = PostForm(
            initial={
                "title": post.editor_title,
                "body": post.editor_body,
                "oposiciones": post.oposiciones.all(),
            }
        )
    return render(request, "posts/post_form.html", _editor_context(request, form, post))


@login_required
@require_POST
def post_autosave(request: HttpRequest) -> JsonResponse:
    """Autosave endpoint: always writes a draft, never the live post.

    Called by static/js/autosave.js. It is progressive enhancement only — the
    editor works without JavaScript through the explicit save buttons.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "payload"}, status=400)

    title = str(payload.get("title") or "")[:MAX_TITLE_CHARS]
    body = str(payload.get("body") or "")
    if len(body) > MAX_BODY_CHARS:
        return JsonResponse({"ok": False, "error": "too_long"}, status=413)

    raw_id = str(payload.get("post_id") or "")
    if raw_id.isdigit():
        post = Post.objects.filter(pk=int(raw_id), author=request.user).first()
        if post is None:
            raise Http404("Apunte no disponible")
    else:
        if not title.strip() and not body.strip():
            # Nothing typed yet: do not create empty rows.
            return JsonResponse({"ok": False, "error": "empty"}, status=200)
        post = Post(author=request.user, status=Post.Status.DRAFT, draft_title=title)
        post.save()

    post.save_draft(title, body)
    saved_at = timezone.localtime(post.draft_saved_at or timezone.now())
    return JsonResponse(
        {
            "ok": True,
            "post_id": post.pk,
            "status": post.status,
            "saved_at": saved_at.isoformat(),
            "saved_at_display": date_format(saved_at, "H:i:s"),
            "edit_url": f"/apuntes/{post.pk}/editar/",
        }
    )


@login_required
@require_POST
def post_publish(request: HttpRequest, pk: int) -> HttpResponse:
    post = get_object_or_404(Post, pk=pk, author=request.user)
    if not (post.editor_title.strip() and post.editor_body.strip()):
        messages.error(request, "Un apunte necesita título y texto antes de publicarse.")
        return redirect("posts:edit", pk=post.pk)
    post.publish()
    messages.success(request, "Apunte publicado.")
    return redirect(post.get_absolute_url())


@login_required
@require_POST
def post_unpublish(request: HttpRequest, pk: int) -> HttpResponse:
    post = get_object_or_404(Post, pk=pk, author=request.user)
    post.unpublish()
    messages.success(request, "Apunte devuelto a borradores.")
    return redirect("posts:mine")


@login_required
@require_POST
def post_delete(request: HttpRequest, pk: int) -> HttpResponse:
    post = get_object_or_404(Post, pk=pk, author=request.user)
    post.delete()
    messages.success(request, "Apunte eliminado.")
    return redirect("posts:mine")


@login_required
def my_posts(request: HttpRequest) -> HttpResponse:
    posts = Post.objects.filter(author=request.user).prefetch_related("oposiciones")
    return render(
        request,
        "posts/my_posts.html",
        {
            "drafts": [p for p in posts if p.status == Post.Status.DRAFT],
            "published": [p for p in posts if p.status == Post.Status.PUBLISHED],
            "meta_title": "Mis apuntes",
            # Author dashboards are thin and private: noindex.
            "noindex": True,
            "hide_ads": True,
        },
    )
