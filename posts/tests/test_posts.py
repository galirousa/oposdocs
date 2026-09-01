"""Posts: the draft/published axis, autosave, and the public rendering
guarantee (formatted content present in the initial HTML response)."""

import json

import pytest

from accounts.factories import UserFactory
from posts.factories import DraftPostFactory, PostFactory
from posts.models import Post

pytestmark = pytest.mark.django_db


class TestModel:
    def test_body_html_is_rendered_on_save(self):
        post = PostFactory(body="Un **apunte** con formato.")
        assert "<strong>apunte</strong>" in post.body_html

    def test_publishing_promotes_the_working_copy(self):
        post = DraftPostFactory(title="", body="")
        post.save_draft("Tema 5: el acto administrativo", "Contenido **definitivo**.")
        post.publish()
        post.refresh_from_db()
        assert post.status == Post.Status.PUBLISHED
        assert post.title == "Tema 5: el acto administrativo"
        assert "<strong>definitivo</strong>" in post.body_html
        assert post.published_at is not None
        assert post.slug == "tema-5-el-acto-administrativo"

    def test_saving_a_draft_does_not_touch_the_published_content(self):
        post = PostFactory(title="Título publicado", body="Texto publicado.")
        post.save_draft("Título nuevo", "Texto nuevo.")
        post.refresh_from_db()
        assert post.title == "Título publicado"
        assert "Texto publicado." in post.body_html
        assert post.has_unpublished_changes
        assert post.editor_title == "Título nuevo"

    def test_slug_is_immutable_once_published(self):
        post = PostFactory(title="Primer título")
        original = post.slug
        post.save_draft("Un título completamente distinto", post.body)
        post.publish()
        post.refresh_from_db()
        assert post.title == "Un título completamente distinto"
        assert post.slug == original

    def test_draft_slug_follows_the_title_until_publication(self):
        post = DraftPostFactory(title="Borrador inicial", draft_saved_at=None)
        assert post.slug == "borrador-inicial"
        post.title = "Borrador renombrado"
        post.save()
        assert post.slug == "borrador-renombrado"

    def test_reserved_slugs_are_not_shadowed(self):
        post = DraftPostFactory(title="Nuevo", draft_saved_at=None)
        assert post.slug == "nuevo-apunte"

    def test_slug_collisions_get_a_suffix(self):
        first = PostFactory(title="Mismo título")
        second = PostFactory(title="Mismo título")
        assert first.slug != second.slug

    def test_thin_posts_are_not_indexable(self):
        assert not PostFactory(body="Dos palabras.").is_indexable
        assert PostFactory().is_indexable

    def test_drafts_are_never_publicly_visible(self):
        assert not DraftPostFactory().is_publicly_visible

    def test_author_display_never_leaks_the_email(self):
        post = PostFactory(author=UserFactory(username="opositora", email="a@example.com"))
        assert post.author_display == "opositora"
        assert "@" not in post.author_display

    def test_unpublish_keeps_published_at_so_the_url_stays_frozen(self):
        post = PostFactory()
        published_at, slug = post.published_at, post.slug
        post.unpublish()
        post.refresh_from_db()
        assert post.status == Post.Status.DRAFT
        assert post.published_at == published_at
        assert post.slug == slug


class TestPublicRendering:
    def test_anonymous_reader_gets_the_formatted_post_in_the_first_response(self, client):
        post = PostFactory(
            title="Cómo preparar el bloque de Derecho Administrativo",
            body=(
                "## Punto de partida\n\n"
                "El acto administrativo es **el concepto central** del bloque, y "
                "conviene tenerlo claro antes de entrar en el procedimiento: la "
                "mayoría de las preguntas del examen giran alrededor de sus "
                "elementos y de sus requisitos de validez.\n\n"
                "- Elementos del acto\n- Requisitos de validez\n\n"
                "> Repasa el esquema cada semana.\n"
            ),
        )
        response = client.get(post.get_absolute_url())
        assert response.status_code == 200
        html = response.content.decode()
        # Rendered markup, not markdown source: no JS needed to read this page.
        assert "<h3>Punto de partida</h3>" in html
        assert "<strong>el concepto central</strong>" in html
        assert "<li>Elementos del acto</li>" in html
        assert "<blockquote>" in html
        assert "**" not in html.split('class="post-body"')[1].split("</div>")[0]
        assert '"@type": "Article"' in html  # JSON-LD in the same response

    def test_published_post_is_indexable(self, client):
        post = PostFactory()
        html = client.get(post.get_absolute_url()).content.decode()
        assert 'name="robots"' not in html

    def test_draft_is_noindex_and_private(self, client):
        post = DraftPostFactory()
        # Anonymous: bounced to login, never a 200.
        assert client.get(post.get_absolute_url()).status_code == 302
        # A different user: 404, the draft does not exist for them.
        client.force_login(UserFactory())
        assert client.get(post.get_absolute_url()).status_code == 404
        # The author: visible, with noindex.
        client.force_login(post.author)
        response = client.get(post.get_absolute_url())
        assert response.status_code == 200
        assert 'content="noindex,follow"' in response.content.decode()

    def test_taken_down_post_is_410(self, client):
        post = PostFactory(moderation_status=Post.ModerationStatus.TAKEN_DOWN)
        assert client.get(post.get_absolute_url()).status_code == 410

    def test_list_shows_only_published_posts(self, client):
        published = PostFactory(title="Apunte publicado")
        draft = DraftPostFactory()
        flagged = PostFactory(
            title="Apunte señalado", moderation_status=Post.ModerationStatus.FLAGGED
        )
        html = client.get("/apuntes/").content.decode()
        assert published.display_title in html
        assert draft.display_title not in html
        assert flagged.display_title not in html

    def test_markdown_negotiation_returns_the_source(self, client):
        post = PostFactory(body="Un **apunte** con formato.")
        response = client.get(f"/apuntes/{post.slug}.md")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/markdown")
        assert "Un **apunte** con formato." in response.content.decode()

    def test_sitemap_contains_published_posts_only(self, client):
        published = PostFactory()
        draft = DraftPostFactory()
        thin = PostFactory(body="Corto.")
        xml = client.get("/sitemap-apuntes.xml").content.decode()
        assert published.get_absolute_url() in xml
        assert draft.get_absolute_url() not in xml
        assert thin.get_absolute_url() not in xml


class TestEditor:
    def test_editor_requires_login(self, client):
        response = client.get("/apuntes/nuevo/")
        assert response.status_code == 302
        # allauth lives at /cuentas/, not Django's default /accounts/.
        assert response["Location"].startswith("/cuentas/login/")

    def test_create_and_publish_without_javascript(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.post(
            "/apuntes/nuevo/",
            {
                "title": "Esquema del tema 1",
                "body": "Un cuerpo con **formato** suficiente para el examen.",
                "action": "publish",
            },
            follow=True,
        )
        assert response.status_code == 200
        post = Post.objects.get(author=user)
        assert post.status == Post.Status.PUBLISHED
        assert "<strong>formato</strong>" in post.body_html

    def test_saving_a_draft_does_not_publish(self, client):
        user = UserFactory()
        client.force_login(user)
        client.post(
            "/apuntes/nuevo/",
            {"title": "A medias", "body": "Sin terminar.", "action": "draft"},
        )
        post = Post.objects.get(author=user)
        assert post.status == Post.Status.DRAFT
        assert post.draft_title == "A medias"
        assert post.title == ""

    def test_publishing_requires_a_title_and_a_body(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.post("/apuntes/nuevo/", {"title": "", "body": "", "action": "publish"})
        assert response.status_code == 200  # form redisplayed
        assert not Post.objects.exists()

    def test_cannot_edit_someone_elses_post(self, client):
        post = PostFactory()
        client.force_login(UserFactory())
        assert client.get(f"/apuntes/{post.pk}/editar/").status_code == 404

    def test_editor_prefills_the_working_copy(self, client):
        post = PostFactory(title="Publicado", body="Cuerpo publicado.")
        post.save_draft("Borrador en curso", "Cuerpo del borrador.")
        client.force_login(post.author)
        html = client.get(f"/apuntes/{post.pk}/editar/").content.decode()
        assert "Borrador en curso" in html
        assert "Cuerpo del borrador." in html

    def test_delete_only_by_the_author(self, client):
        post = DraftPostFactory()
        client.force_login(UserFactory())
        assert client.post(f"/apuntes/{post.pk}/eliminar/").status_code == 404
        client.force_login(post.author)
        client.post(f"/apuntes/{post.pk}/eliminar/")
        assert not Post.objects.filter(pk=post.pk).exists()


class TestAutosave:
    def _autosave(self, client, **payload):
        return client.post(
            "/apuntes/autoguardar/", data=json.dumps(payload), content_type="application/json"
        )

    def test_autosave_requires_login(self, client):
        response = self._autosave(client, title="Hola", body="Mundo")
        assert response.status_code == 302

    def test_autosave_creates_a_draft_and_returns_its_id(self, client):
        user = UserFactory()
        client.force_login(user)
        response = self._autosave(client, title="Tema 3", body="Primeras notas.")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["status"] == Post.Status.DRAFT
        post = Post.objects.get(pk=data["post_id"])
        assert post.author == user
        assert post.status == Post.Status.DRAFT
        assert post.draft_body == "Primeras notas."
        # Nothing about it is public yet.
        assert not post.is_publicly_visible

    def test_repeated_autosaves_update_the_same_draft(self, client):
        user = UserFactory()
        client.force_login(user)
        first = self._autosave(client, title="Tema 3", body="Primeras notas.").json()
        second = self._autosave(
            client, post_id=first["post_id"], title="Tema 3", body="Notas ampliadas."
        ).json()
        assert first["post_id"] == second["post_id"]
        assert Post.objects.filter(author=user).count() == 1
        assert Post.objects.get(pk=first["post_id"]).draft_body == "Notas ampliadas."

    def test_autosave_never_changes_what_readers_see(self, client):
        post = PostFactory(title="Título publicado", body="Texto publicado original.")
        client.force_login(post.author)
        self._autosave(client, post_id=post.pk, title="Otro título", body="Texto reescrito.")
        post.refresh_from_db()
        assert post.status == Post.Status.PUBLISHED
        assert post.title == "Título publicado"
        assert "Texto publicado original." in post.body_html
        assert post.draft_body == "Texto reescrito."

    def test_autosave_on_an_empty_editor_creates_nothing(self, client):
        client.force_login(UserFactory())
        response = self._autosave(client, title="  ", body="")
        assert response.status_code == 200
        assert response.json()["ok"] is False
        assert not Post.objects.exists()

    def test_autosave_cannot_touch_another_users_post(self, client):
        post = DraftPostFactory()
        client.force_login(UserFactory())
        response = self._autosave(client, post_id=post.pk, title="Secuestrado", body="x")
        assert response.status_code == 404
        post.refresh_from_db()
        assert post.draft_title != "Secuestrado"

    def test_oversized_body_is_rejected(self, client):
        client.force_login(UserFactory())
        response = self._autosave(client, title="Enorme", body="x" * 100_001)
        assert response.status_code == 413
        assert not Post.objects.exists()

    def test_malformed_payload_is_rejected(self, client):
        client.force_login(UserFactory())
        response = client.post(
            "/apuntes/autoguardar/", data="no es json", content_type="application/json"
        )
        assert response.status_code == 400

    def test_autosaved_draft_can_then_be_published(self, client):
        user = UserFactory()
        client.force_login(user)
        data = self._autosave(
            client, title="Tema 4", body="Notas suficientemente largas para publicar."
        ).json()
        client.post(f"/apuntes/{data['post_id']}/publicar/")
        post = Post.objects.get(pk=data["post_id"])
        assert post.status == Post.Status.PUBLISHED
        assert post.title == "Tema 4"
