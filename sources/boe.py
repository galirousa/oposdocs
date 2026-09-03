"""Client for the BOE open-data summary API.

    https://www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD

Three quirks of that API drive the shape of this module, all confirmed against
the live service:

1. A day with no edition (Sundays, most public holidays) answers **404 with an
   XML body**, even when the request asks for JSON. Never parse before checking
   the status code.
2. ``epigrafe`` hangs off ``departamento`` in section 2B but off
   ``departamento.texto`` in section 1. Both shapes appear in one response.
3. ``departamento``, ``epigrafe`` and ``item`` are each a dict when there is one
   of them and a list when there are several. Everything goes through
   :func:`_as_list`.

This module is pure I/O + parsing: no database, no Celery, so it can be tested
against a saved fixture.
"""

import dataclasses
import datetime as dt
import logging
from collections.abc import Iterator
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SUMMARY_URL = "https://www.boe.es/datosabiertos/api/boe/sumario/{day}"

# "II. Autoridades y personal. - B. Oposiciones y concursos" — the whole reason
# this harvester exists. Section codes are stable BOE identifiers.
SECTION_OPOSICIONES = "2B"


class NoEditionError(Exception):
    """No bulletin published on that date (Sunday, holiday, or a future date)."""


class BoeUnavailableError(Exception):
    """Transport or server-side failure; the caller should retry later."""


@dataclasses.dataclass(frozen=True)
class BoeItem:
    """One numbered item in the summary. ``identificador`` is BOE's own stable
    key (``BOE-A-2026-18371``) and is what makes re-harvesting idempotent."""

    identificador: str
    titulo: str
    seccion: str
    departamento: str
    epigrafe: str
    url_pdf: str
    url_html: str
    url_xml: str
    size_bytes: int
    fecha_publicacion: dt.date


def _as_list(value: Any) -> list[Any]:
    """BOE gives a dict for one child and a list for several."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "User-Agent": settings.HARVEST_USER_AGENT,
    }


def fetch_summary(day: dt.date) -> dict[str, Any]:
    """Return the parsed summary for ``day``.

    Raises :class:`NoEditionError` when there is no bulletin, and
    :class:`BoeUnavailableError` for anything the caller should retry.
    """
    url = SUMMARY_URL.format(day=day.strftime("%Y%m%d"))
    try:
        response = requests.get(url, headers=_headers(), timeout=(10, 60))
    except requests.RequestException as exc:
        raise BoeUnavailableError(f"BOE request failed for {day}: {exc}") from exc

    if response.status_code == 404:
        raise NoEditionError(f"No BOE edition published on {day}")
    if response.status_code >= 400:
        raise BoeUnavailableError(f"BOE returned HTTP {response.status_code} for {day}")
    try:
        return response.json()
    except ValueError as exc:
        # A non-JSON 200 means the service is having a bad day; treat it as
        # retryable rather than as an empty edition.
        raise BoeUnavailableError(f"BOE returned a non-JSON body for {day}") from exc


def iter_items(payload: dict[str, Any], *, section: str = SECTION_OPOSICIONES) -> Iterator[BoeItem]:
    """Walk the summary and yield every item in ``section``."""
    sumario = (payload.get("data") or {}).get("sumario") or {}
    metadatos = sumario.get("metadatos") or {}
    fecha = _parse_day(metadatos.get("fecha_publicacion"))

    for diario in _as_list(sumario.get("diario")):
        for seccion in _as_list(diario.get("seccion")):
            if seccion.get("codigo") != section:
                continue
            seccion_nombre = seccion.get("nombre", "")
            for departamento in _as_list(seccion.get("departamento")):
                dep_nombre = departamento.get("nombre", "")
                # Quirk 2: epigrafe sits either directly on the departamento or
                # one level down under "texto".
                epigrafes = departamento.get("epigrafe")
                if epigrafes is None:
                    epigrafes = (departamento.get("texto") or {}).get("epigrafe")
                for epigrafe in _as_list(epigrafes):
                    ep_nombre = epigrafe.get("nombre", "")
                    for item in _as_list(epigrafe.get("item")):
                        parsed = _build_item(item, seccion_nombre, dep_nombre, ep_nombre, fecha)
                        if parsed is not None:
                            yield parsed


def _build_item(
    item: dict[str, Any],
    seccion: str,
    departamento: str,
    epigrafe: str,
    fecha: dt.date,
) -> BoeItem | None:
    identificador = item.get("identificador")
    if not identificador:
        logger.warning("BOE item without identificador in %s; skipped", departamento)
        return None
    pdf = item.get("url_pdf") or {}
    if isinstance(pdf, str):  # defensive: shape has varied historically
        pdf = {"texto": pdf}
    return BoeItem(
        identificador=identificador,
        titulo=(item.get("titulo") or "").strip(),
        seccion=seccion,
        departamento=departamento,
        epigrafe=epigrafe,
        url_pdf=pdf.get("texto", ""),
        url_html=item.get("url_html", "") or "",
        url_xml=item.get("url_xml", "") or "",
        size_bytes=int(pdf.get("szBytes") or 0),
        fecha_publicacion=fecha,
    )


def _parse_day(raw: str | None) -> dt.date:
    if not raw:
        raise BoeUnavailableError("Summary is missing fecha_publicacion")
    return dt.datetime.strptime(raw, "%Y%m%d").date()


def download(url: str, *, max_bytes: int | None = None) -> bytes:
    """Download one document, refusing anything over the size ceiling.

    Streamed and size-checked so a pathological 400 MB annex cannot exhaust the
    worker's memory on a machine this small.
    """
    ceiling = max_bytes if max_bytes is not None else settings.HARVEST_MAX_PDF_BYTES
    try:
        with requests.get(url, headers=_headers(), timeout=(10, 120), stream=True) as response:
            if response.status_code >= 400:
                raise BoeUnavailableError(f"HTTP {response.status_code} downloading {url}")
            declared = int(response.headers.get("Content-Length") or 0)
            if declared and declared > ceiling:
                raise ValueError(f"{url} is {declared} bytes, over the {ceiling} ceiling")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(1024 * 256):
                total += len(chunk)
                if total > ceiling:
                    raise ValueError(f"{url} exceeded the {ceiling} byte ceiling mid-download")
                chunks.append(chunk)
    except requests.RequestException as exc:
        raise BoeUnavailableError(f"Download failed for {url}: {exc}") from exc
    return b"".join(chunks)
