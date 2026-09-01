import pytest

from documents.factories import DocumentFactory
from oposiciones.factories import OposicionFactory
from search.backends import get_backend

pytestmark = pytest.mark.django_db


@pytest.fixture
def corpus():
    op = OposicionFactory(nombre="Auxiliar Administrativo", grupo="C2", is_featured=True)
    doc1 = DocumentFactory(
        title="Temario de la oposición a Auxiliar Administrativo",
        description="Temario completo del Cuerpo General Auxiliar.",
        extracted_text="La Constitución Española y el procedimiento administrativo común.",
        oposiciones=[op],
    )
    doc2 = DocumentFactory(
        title="Apuntes de informática básica",
        description="Bloque de ofimática.",
        extracted_text="Hardware, software, Word y Excel para la administración.",
        oposiciones=[op],
    )
    hidden = DocumentFactory(
        title="Borrador pendiente sobre auxiliares",
        moderation_status="pending",
        oposiciones=[op],
    )
    backend = get_backend()
    for doc in (doc1, doc2, hidden):
        backend.index(doc)
        doc.refresh_from_db()
    return op, doc1, doc2, hidden


class TestAccentInsensitivity:
    def test_accented_and_unaccented_queries_match(self, corpus):
        backend = get_backend()
        plain = backend.query("oposicion auxiliar")
        accented = backend.query("oposición auxiliar")
        assert plain.total > 0
        assert plain.total == accented.total
        assert [r.document.pk for r in plain.results] == [r.document.pk for r in accented.results]

    def test_query_with_wrong_accent_still_matches(self, corpus):
        backend = get_backend()
        assert backend.query("administrativó").total == backend.query("administrativo").total


class TestFiltersAndVisibility:
    def test_pending_documents_never_surface(self, corpus):
        results = get_backend().query("auxiliares borrador pendiente")
        assert all(r.document.moderation_status == "approved" for r in results.results)

    def test_facet_filter_by_grupo(self, corpus):
        results = get_backend().query("auxiliar", filters={"grupo": "C2"})
        assert results.total >= 1
        none = get_backend().query("auxiliar", filters={"grupo": "A1"})
        assert none.total == 0

    def test_weighting_prefers_title_match(self, corpus):
        _, doc1, _, _ = corpus
        results = get_backend().query("auxiliar administrativo")
        assert results.results[0].document.pk == doc1.pk


class TestSearchPage:
    def test_server_rendered_results(self, client, corpus):
        response = client.get("/buscar/", {"q": "auxiliar administrativo"})
        assert response.status_code == 200
        html = response.content.decode()
        assert "Temario de la oposición a Auxiliar Administrativo" in html
        assert 'content="noindex,follow"' in html

    def test_empty_state_suggests_popular(self, client, corpus):
        html = client.get("/buscar/", {"q": "zzzzinexistente"}).content.decode()
        assert "Oposiciones populares" in html


class TestApi:
    def test_json_results(self, client, corpus):
        response = client.get("/api/buscar/", {"q": "auxiliar"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] >= 1
        assert payload["results"][0]["url"].startswith("http")

    def test_missing_query_400(self, client):
        assert client.get("/api/buscar/").status_code == 400

    def test_schema_endpoint(self, client):
        payload = client.get("/api/schema/").json()
        assert payload["openapi"].startswith("3.")
        assert "/api/buscar/" in payload["paths"]
