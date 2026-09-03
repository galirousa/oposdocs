"""Parser tests against a trimmed copy of a real BOE response.

The fixture is a real summary (2026-09-01) cut down to two departments, and it
deliberately keeps all three shape quirks the live API produces: one department
whose ``epigrafe`` is a list, one whose ``epigrafe`` is a bare dict, and a
section 1 department whose epígrafes hang off ``texto`` instead.
"""

import datetime as dt
import json
from pathlib import Path
from unittest import mock

import pytest
import requests

from sources import boe

FIXTURE = Path(__file__).parent / "fixtures" / "boe_sumario_20260901.json"


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text())


class TestIterItems:
    def test_yields_every_oposiciones_item(self, payload):
        items = list(boe.iter_items(payload))
        assert len(items) == 4

    def test_handles_dict_and_list_shapes(self, payload):
        # Departments appear in both shapes in the fixture; if _as_list were
        # wrong, one of these two groups would be missing entirely.
        departments = {item.departamento for item in boe.iter_items(payload)}
        assert len(departments) == 2

    def test_populates_every_field(self, payload):
        item = next(iter(boe.iter_items(payload)))
        assert item.identificador.startswith("BOE-A-2026-")
        assert item.titulo
        assert item.url_pdf.endswith(".pdf")
        assert item.url_html.startswith("https://")
        assert item.size_bytes > 0
        assert item.fecha_publicacion == dt.date(2026, 9, 1)
        assert "Oposiciones y concursos" in item.seccion

    def test_ignores_other_sections(self, payload):
        identifiers = {item.identificador for item in boe.iter_items(payload)}
        section_one = {item.identificador for item in boe.iter_items(payload, section="1")}
        assert section_one
        assert not identifiers & section_one

    def test_reads_epigrafe_nested_under_texto(self, payload):
        """Section 1 uses departamento.texto.epigrafe; the walker must cope."""
        items = list(boe.iter_items(payload, section="1"))
        assert items and all(item.titulo for item in items)

    def test_item_without_identificador_is_skipped(self, payload):
        seccion = payload["data"]["sumario"]["diario"][0]["seccion"][1]
        departamento = seccion["departamento"][0]
        epigrafe = departamento["epigrafe"][0]
        items = epigrafe["item"]
        items = items if isinstance(items, list) else [items]
        items.append({"titulo": "Sin identificador"})
        epigrafe["item"] = items
        assert len(list(boe.iter_items(payload))) == 4


def _response(status: int, *, json_body=None, text: str = ""):
    response = mock.Mock(spec=requests.Response)
    response.status_code = status
    response.text = text
    if json_body is None:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = json_body
    return response


class TestFetchSummary:
    def test_returns_payload(self, payload):
        with mock.patch.object(boe.requests, "get", return_value=_response(200, json_body=payload)):
            assert boe.fetch_summary(dt.date(2026, 9, 1)) == payload

    def test_404_is_no_edition_even_though_the_body_is_xml(self):
        """Sundays answer 404 with XML; parsing before checking status would blow up."""
        xml = '<?xml version="1.0"?><response><status><code>404</code></status></response>'
        with (
            mock.patch.object(boe.requests, "get", return_value=_response(404, text=xml)),
            pytest.raises(boe.NoEditionError),
        ):
            boe.fetch_summary(dt.date(2026, 8, 30))

    def test_server_error_is_retryable(self):
        with (
            mock.patch.object(boe.requests, "get", return_value=_response(503)),
            pytest.raises(boe.BoeUnavailableError),
        ):
            boe.fetch_summary(dt.date(2026, 9, 1))

    def test_non_json_200_is_retryable_not_empty(self):
        with (
            mock.patch.object(boe.requests, "get", return_value=_response(200, text="<html>")),
            pytest.raises(boe.BoeUnavailableError),
        ):
            boe.fetch_summary(dt.date(2026, 9, 1))

    def test_connection_error_is_retryable(self):
        with (
            mock.patch.object(boe.requests, "get", side_effect=requests.Timeout("slow")),
            pytest.raises(boe.BoeUnavailableError),
        ):
            boe.fetch_summary(dt.date(2026, 9, 1))


class _StreamResponse:
    def __init__(self, chunks, headers=None, status=200):
        self._chunks = chunks
        self.headers = headers or {}
        self.status_code = status

    def iter_content(self, size):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestDownload:
    def test_returns_bytes(self):
        with mock.patch.object(
            boe.requests, "get", return_value=_StreamResponse([b"%PDF-", b"data"])
        ):
            assert boe.download("https://example.test/a.pdf") == b"%PDF-data"

    def test_refuses_declared_oversize(self):
        response = _StreamResponse([b"x"], headers={"Content-Length": "999999999"})
        with (
            mock.patch.object(boe.requests, "get", return_value=response),
            pytest.raises(ValueError, match="ceiling"),
        ):
            boe.download("https://example.test/big.pdf", max_bytes=1000)

    def test_refuses_oversize_discovered_mid_stream(self):
        """No Content-Length is the case that would otherwise OOM the worker."""
        response = _StreamResponse([b"x" * 600, b"x" * 600])
        with (
            mock.patch.object(boe.requests, "get", return_value=response),
            pytest.raises(ValueError, match="ceiling"),
        ):
            boe.download("https://example.test/big.pdf", max_bytes=1000)

    def test_http_error_is_retryable(self):
        with (
            mock.patch.object(boe.requests, "get", return_value=_StreamResponse([], status=500)),
            pytest.raises(boe.BoeUnavailableError),
        ):
            boe.download("https://example.test/a.pdf")
