"""Discoverability contract: the raw HTML must contain the full factual
answer with JavaScript disabled, plus valid structured data."""

import json
from datetime import date, timedelta

import pytest

from oposiciones.factories import ConvocatoriaFactory, OposicionFactory, TemaFactory

pytestmark = pytest.mark.django_db


def _jsonld_blocks(html: str) -> list[dict]:
    blocks = []
    remainder = html
    marker = '<script type="application/ld+json">'
    while marker in remainder:
        _, _, remainder = remainder.partition(marker)
        body, _, remainder = remainder.partition("</script>")
        blocks.append(json.loads(body))
    return blocks


@pytest.fixture
def oposicion():
    op = OposicionFactory(nombre="Auxiliar Administrativo", grupo="C2", is_featured=True)
    ConvocatoriaFactory(
        oposicion=op,
        anio=2026,
        plazas=2856,
        estado="abierta",
        fecha_publicacion=date.today() - timedelta(days=30),
        fecha_limite_solicitud=date.today() + timedelta(days=60),
    )
    TemaFactory(oposicion=op, numero=1, titulo="La Constitución Española de 1978")
    return op


class TestOposicionPage:
    def test_answer_first_in_raw_html(self, client, oposicion):
        response = client.get(oposicion.get_absolute_url())
        assert response.status_code == 200
        html = response.content.decode()
        # The full factual answer is in the initial HTML: no JS required.
        assert oposicion.answer_paragraph in html
        assert "<dl" in html
        assert '<html lang="es">' in html

    def test_canonical_and_meta(self, client, oposicion, settings):
        html = client.get(oposicion.get_absolute_url()).content.decode()
        assert (
            f'<link rel="canonical" href="{settings.SITE_URL}{oposicion.get_absolute_url()}"'
            in html
        )
        assert 'property="og:title"' in html
        assert "noindex" not in html

    def test_jsonld_collectionpage_and_breadcrumbs(self, client, oposicion):
        html = client.get(oposicion.get_absolute_url()).content.decode()
        blocks = _jsonld_blocks(html)
        types = {b["@type"] for b in blocks}
        assert "CollectionPage" in types
        assert "BreadcrumbList" in types

    def test_unpublished_is_404(self, client):
        op = OposicionFactory(is_published=False)
        assert client.get(f"/oposiciones/{op.ambito}/{op.slug}/").status_code == 404


class TestConvocatoriaPage:
    def test_jobposting_when_open(self, client, oposicion):
        conv = oposicion.convocatorias.first()
        html = client.get(conv.get_absolute_url()).content.decode()
        jobs = [b for b in _jsonld_blocks(html) if b["@type"] == "JobPosting"]
        assert len(jobs) == 1
        job = jobs[0]
        for field in (
            "title",
            "description",
            "datePosted",
            "validThrough",
            "hiringOrganization",
            "jobLocation",
            "employmentType",
        ):
            assert field in job, f"JobPosting missing required field {field}"

    def test_no_jobposting_when_closed(self, client):
        conv = ConvocatoriaFactory(
            estado="resuelta", fecha_limite_solicitud=date.today() - timedelta(days=10)
        )
        html = client.get(conv.get_absolute_url()).content.decode()
        assert not [b for b in _jsonld_blocks(html) if b["@type"] == "JobPosting"]

    def test_no_jobposting_when_deadline_past(self, client):
        conv = ConvocatoriaFactory(
            estado="abierta", fecha_limite_solicitud=date.today() - timedelta(days=1)
        )
        html = client.get(conv.get_absolute_url()).content.decode()
        assert not [b for b in _jsonld_blocks(html) if b["@type"] == "JobPosting"]


class TestMarkdownNegotiation:
    def test_oposicion_page_as_markdown(self, client, oposicion):
        url = oposicion.get_absolute_url().rstrip("/") + ".md"
        response = client.get(url)
        assert response.status_code == 200
        assert "text/markdown" in response["Content-Type"]
        body = response.content.decode()
        assert body.startswith(f"# Oposición a {oposicion.derived_title}")
        assert "| Dato | Valor |" in body
        assert "<html" not in body

    def test_homepage_as_markdown(self, client, oposicion):
        response = client.get("/.md")
        assert response.status_code == 200
        assert "text/markdown" in response["Content-Type"]

    def test_facets_are_noindex(self, client, oposicion):
        html = client.get("/oposiciones/?ambito=estado").content.decode()
        assert 'content="noindex,follow"' in html
        assert 'rel="canonical" href="http://localhost:8000/oposiciones/"' in html
