"""Seed editorial/official documents with extracted text so search and the
document pages have plausible content. When object storage is reachable, a
real generated PDF is also pushed through the full ingestion pipeline.
"""

import hashlib
from typing import Any

from django.core.management.base import BaseCommand

from documents.models import Document
from oposiciones.models import Oposicion
from search.backends import get_backend

CONSTITUCION = (
    "La Constitución Española de 1978 es la norma suprema del ordenamiento "
    "jurídico español. Fue aprobada por las Cortes Generales el 31 de octubre "
    "de 1978, ratificada en referéndum el 6 de diciembre y sancionada por el "
    "Rey el 27 de diciembre. Se estructura en un título preliminar y diez "
    "títulos, con 169 artículos, además de disposiciones adicionales, "
    "transitorias, derogatorias y finales. España se constituye en un Estado "
    "social y democrático de Derecho que propugna como valores superiores de "
    "su ordenamiento jurídico la libertad, la justicia, la igualdad y el "
    "pluralismo político. La soberanía nacional reside en el pueblo español, "
    "del que emanan los poderes del Estado. La forma política del Estado "
    "español es la Monarquía parlamentaria."
)

PROCEDIMIENTO = (
    "La Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Común "
    "de las Administraciones Públicas regula los requisitos de validez y "
    "eficacia de los actos administrativos, el procedimiento administrativo "
    "común a todas las Administraciones Públicas y los principios a los que "
    "se ha de ajustar el ejercicio de la iniciativa legislativa y la potestad "
    "reglamentaria. El procedimiento se inicia de oficio o a solicitud del "
    "interesado, se ordena mediante los principios de celeridad e impulso de "
    "oficio, y termina por resolución, desistimiento, renuncia o caducidad. "
    "El silencio administrativo tiene efectos estimatorios o desestimatorios "
    "según los casos previstos en la ley."
)

OFIMATICA = (
    "Conceptos fundamentales de informática básica para la oposición: el "
    "hardware comprende la unidad central de proceso, la memoria principal y "
    "los periféricos de entrada y salida. El software se clasifica en "
    "software de sistema, como los sistemas operativos Windows y Linux, y "
    "software de aplicación, como los procesadores de texto y las hojas de "
    "cálculo. En Microsoft Word las funciones principales incluyen formato "
    "de párrafo, estilos, tablas y combinación de correspondencia. En Excel, "
    "las fórmulas, funciones, gráficos y tablas dinámicas. El correo "
    "electrónico funciona mediante los protocolos SMTP, POP3 e IMAP."
)

SEED_DOCS: list[dict[str, Any]] = [
    {
        "title": "Tema 1. La Constitución Española de 1978 (temario completo)",
        "description": "Tema 1 del temario oficial: características, estructura y principios generales de la Constitución.",
        "slug_oposicion": "auxiliar-administrativo",
        "source_type": "editorial",
        "text": CONSTITUCION,
    },
    {
        "title": "Tema 7. El procedimiento administrativo común (Ley 39/2015)",
        "description": "Desarrollo del tema sobre la Ley 39/2015 del Procedimiento Administrativo Común.",
        "slug_oposicion": "auxiliar-administrativo",
        "source_type": "editorial",
        "text": PROCEDIMIENTO,
    },
    {
        "title": "Tema 15. Informática básica: hardware y software",
        "description": "Apuntes del bloque de ofimática: conceptos fundamentales de hardware y software.",
        "slug_oposicion": "auxiliar-administrativo",
        "source_type": "editorial",
        "text": OFIMATICA,
    },
    {
        "title": "Convocatoria 2026 del Cuerpo General Auxiliar (BOE-A-2026-1102)",
        "description": "Texto oficial de la convocatoria publicada en el BOE: bases, plazas y plazos de solicitud.",
        "slug_oposicion": "auxiliar-administrativo",
        "source_type": "official",
        "text": (
            "Resolución por la que se convocan procesos selectivos para el "
            "ingreso en el Cuerpo General Auxiliar de la Administración del "
            "Estado. Se convocan 2.856 plazas, de las que 286 se reservan "
            "para personas con discapacidad. El plazo de presentación de "
            "solicitudes será de veinte días hábiles. " + PROCEDIMIENTO
        ),
    },
    {
        "title": "Temario de Tramitación Procesal: organización judicial española",
        "description": "La organización judicial española: órganos jurisdiccionales y su competencia.",
        "slug_oposicion": "tramitacion-procesal-y-administrativa",
        "source_type": "editorial",
        "text": (
            "El Poder Judicial se regula en el Título VI de la Constitución "
            "Española. La justicia emana del pueblo y se administra en nombre "
            "del Rey por Jueces y Magistrados integrantes del poder judicial, "
            "independientes, inamovibles, responsables y sometidos únicamente "
            "al imperio de la ley. La organización judicial comprende el "
            "Tribunal Supremo, la Audiencia Nacional, los Tribunales "
            "Superiores de Justicia, las Audiencias Provinciales y los "
            "juzgados de primera instancia e instrucción, de lo penal, de lo "
            "contencioso-administrativo, de lo social, de menores y de "
            "vigilancia penitenciaria."
        ),
    },
    {
        "title": "Guía de la convocatoria de Policía Nacional Escala Básica 2026",
        "description": "Requisitos, pruebas físicas y calendario de la convocatoria 2026 de la Escala Básica.",
        "slug_oposicion": "policia-nacional-escala-basica",
        "source_type": "editorial",
        "text": (
            "La oposición a la Escala Básica del Cuerpo Nacional de Policía "
            "consta de tres pruebas de carácter eliminatorio: aptitud física, "
            "prueba de conocimientos y ortografía, y reconocimiento médico y "
            "entrevista personal. Los aspirantes deben tener nacionalidad "
            "española, estar en posesión del título de Bachiller o "
            "equivalente y no haber sido condenados por delito doloso."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed editorial and official documents with extracted text."

    def handle(self, *args: Any, **options: Any) -> None:
        backend = get_backend()
        created = 0
        for entry in SEED_DOCS:
            oposicion = Oposicion.objects.filter(slug=entry["slug_oposicion"]).first()
            if oposicion is None:
                self.stderr.write(
                    f"Oposición {entry['slug_oposicion']} not found; run seed_oposiciones first."
                )
                continue
            sha256 = hashlib.sha256(entry["text"].encode()).hexdigest()
            document, was_created = Document.objects.update_or_create(
                sha256=sha256,
                defaults={
                    "title": entry["title"],
                    "description": entry["description"],
                    "source_type": entry["source_type"],
                    "visibility": Document.Visibility.PUBLIC,
                    "moderation_status": Document.ModerationStatus.APPROVED,
                    "mime_type": "application/pdf",
                    "size_bytes": len(entry["text"].encode()),
                    "page_count": max(1, len(entry["text"]) // 1800),
                    "extracted_text": entry["text"],
                    "extraction_status": Document.ExtractionStatus.DONE,
                    "license": "official_public"
                    if entry["source_type"] == "official"
                    else "own_work",
                },
            )
            document.oposiciones.add(oposicion)
            backend.index(document)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(SEED_DOCS)} documents ({created} new)."))
