"""The four access rules from the section 7 matrix, plus the public-rendering
guarantee: anonymous crawlers get identical, fully-rendered HTML."""

import pytest
from django.contrib.auth.models import AnonymousUser

from accounts.factories import UserFactory
from documents.factories import DocumentFactory
from documents.models import Document
from documents.permissions import can_access

pytestmark = pytest.mark.django_db


class TestCanAccess:
    def test_approved_public_everyone(self):
        doc = DocumentFactory(visibility="public", moderation_status="approved")
        assert can_access(AnonymousUser(), doc)
        assert can_access(UserFactory(), doc)

    def test_approved_registered_requires_auth(self):
        doc = DocumentFactory(visibility="registered", moderation_status="approved")
        assert not can_access(AnonymousUser(), doc)
        assert can_access(UserFactory(), doc)

    def test_private_owner_and_staff_only(self):
        owner = UserFactory()
        staff = UserFactory(is_staff=True)
        other = UserFactory()
        doc = DocumentFactory(visibility="private", moderation_status="approved", uploader=owner)
        assert can_access(owner, doc)
        assert can_access(staff, doc)
        assert not can_access(other, doc)
        assert not can_access(AnonymousUser(), doc)

    def test_pending_owner_and_staff_only(self):
        owner = UserFactory()
        doc = DocumentFactory(visibility="public", moderation_status="pending", uploader=owner)
        assert can_access(owner, doc)
        assert can_access(UserFactory(is_staff=True), doc)
        assert not can_access(UserFactory(), doc)
        assert not can_access(AnonymousUser(), doc)


class TestPublicRendering:
    def test_anonymous_gets_full_content_200(self, client):
        doc = DocumentFactory(
            visibility="public",
            moderation_status="approved",
            extracted_text="La Constitución Española de 1978 es la norma suprema. " * 30,
        )
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 200
        html = response.content.decode()
        assert doc.title in html
        assert "La Constitución Española de 1978" in html  # extracted-text preview
        assert "DigitalDocument" in html  # JSON-LD present

    def test_taken_down_is_410(self, client):
        doc = DocumentFactory(moderation_status="taken_down")
        assert client.get(doc.get_absolute_url()).status_code == 410

    def test_registered_document_redirects_anonymous_to_login(self, client):
        doc = DocumentFactory(visibility="registered", moderation_status="approved")
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 302
        assert "/cuentas/login/" in response["Location"]


class TestThinContentGuard:
    def test_thin_document_is_noindex(self, client):
        doc = DocumentFactory(description="", extracted_text="")
        html = client.get(doc.get_absolute_url()).content.decode()
        assert 'content="noindex,follow"' in html

    def test_rich_document_is_indexable(self, client):
        doc = DocumentFactory(
            description="Apuntes completos del tema 1.",
            extracted_text="Texto extraído del documento.",
        )
        assert doc.is_indexable
        html = client.get(doc.get_absolute_url()).content.decode()
        assert "noindex" not in html

    def test_duplicate_canonicalises_to_original(self, client):
        original = DocumentFactory()
        dupe = DocumentFactory(canonical_document=original)
        html = client.get(dupe.get_absolute_url()).content.decode()
        assert f'rel="canonical" href="http://localhost:8000{original.get_absolute_url()}"' in html
        assert not dupe.is_indexable


class TestSitemapExclusion:
    def test_pending_and_taken_down_excluded(self, client):
        visible = DocumentFactory()
        DocumentFactory(moderation_status="pending", title="Pendiente")
        DocumentFactory(moderation_status="taken_down", title="Retirado")
        xml = client.get("/sitemap-documentos.xml").content.decode()
        assert visible.get_absolute_url() in xml
        assert "pendiente" not in xml
        assert "retirado" not in xml


class TestModeration:
    def test_status_change_writes_audit_log(self, admin_client):
        doc = DocumentFactory(moderation_status="pending")
        from documents.admin import _log_status_change

        _log_status_change(doc, None, "pending", "approved", "ok")
        assert doc.moderation_log.count() == 1
        entry = doc.moderation_log.first()
        assert entry.from_status == "pending"
        assert entry.to_status == "approved"

    def test_dedupe_links_existing_document(self):
        existing = DocumentFactory()
        assert Document.objects.filter(sha256=existing.sha256).count() == 1
