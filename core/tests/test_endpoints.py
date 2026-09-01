import json

import pytest

from oposiciones.factories import OposicionFactory

pytestmark = pytest.mark.django_db


class TestHealthz:
    def test_healthy(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        payload = json.loads(response.content)
        assert payload["status"] == "ok"
        assert payload["checks"]["database"] == "ok"
        assert payload["checks"]["redis"] == "ok"


class TestRobots:
    def test_allows_ai_crawlers_when_indexing_enabled(self, client):
        body = client.get("/robots.txt").content.decode()
        for bot in ("Googlebot", "GPTBot", "ClaudeBot", "PerplexityBot", "CCBot"):
            assert f"User-agent: {bot}" in body
        assert "Disallow: /admin/" in body
        assert "Sitemap:" in body
        assert "Cloudflare" in body  # operator note about the edge override

    def test_disallows_everything_on_staging(self, client, settings):
        settings.ALLOW_INDEXING = False
        body = client.get("/robots.txt").content.decode()
        assert "Disallow: /" in body
        assert "GPTBot" not in body


class TestLlmsTxt:
    def test_lists_published_oposiciones(self, client):
        op = OposicionFactory(nombre="Auxiliar Administrativo", is_published=True)
        OposicionFactory(nombre="Oculta", is_published=False)
        response = client.get("/llms.txt")
        assert response.status_code == 200
        assert "markdown" in response["Content-Type"]
        body = response.content.decode()
        assert op.derived_title in body
        assert "Oculta" not in body


class TestSitemaps:
    def test_index_and_sections(self, client):
        OposicionFactory(is_published=True)
        assert client.get("/sitemap.xml").status_code == 200
        assert client.get("/sitemap-oposiciones.xml").status_code == 200
        assert client.get("/sitemap-documentos.xml").status_code == 200


class TestConsentLog:
    def test_logs_decision(self, client):
        response = client.post(
            "/consentimiento/registrar/",
            data=json.dumps({"decision": "rejected"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        from core.models import ConsentEvent

        assert ConsentEvent.objects.filter(decision="rejected").count() == 1

    def test_rejects_bad_decision(self, client):
        response = client.post(
            "/consentimiento/registrar/",
            data=json.dumps({"decision": "maybe"}),
            content_type="application/json",
        )
        assert response.status_code == 400
