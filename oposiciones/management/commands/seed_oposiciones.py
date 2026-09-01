"""Load real state-level oposiciones so there is plausible data to build against.

Idempotent: matches on nombre and updates in place.
"""

from datetime import date
from typing import Any

from django.core.management.base import BaseCommand

from oposiciones.models import Convocatoria, Oposicion, Tema

ESO = "Título de Graduado en Educación Secundaria Obligatoria"
BACH = "Título de Bachiller o Técnico"
GRADO = "Título universitario de Grado"
DIPL = "Título de Diplomado, Ingeniero Técnico o Grado"

SEED: list[dict[str, Any]] = [
    {
        "nombre": "Auxiliar Administrativo",
        "cuerpo": "Cuerpo General Auxiliar de la Administración del Estado",
        "grupo": "C2",
        "titulacion": ESO,
        "organismo": "Ministerio de Hacienda y Función Pública",
        "featured": True,
        "order": 1,
        "descripcion": (
            "Tareas administrativas de apoyo: registro, atención al público, "
            "tratamiento de textos y gestión de expedientes en la Administración "
            "General del Estado."
        ),
        "convocatorias": [
            {
                "anio": 2026,
                "referencia_boe": "BOE-A-2026-1102",
                "plazas": 2856,
                "plazas_libre": 2570,
                "plazas_discapacidad": 286,
                "fecha_publicacion": date(2026, 1, 20),
                "fecha_limite": date(2026, 12, 15),
                "estado": "abierta",
            },
            {
                "anio": 2024,
                "referencia_boe": "BOE-A-2024-9931",
                "plazas": 2296,
                "fecha_publicacion": date(2024, 5, 14),
                "fecha_limite": date(2024, 6, 11),
                "estado": "resuelta",
            },
        ],
        "temas": [
            (
                1,
                "La Constitución Española de 1978: características, estructura y principios generales",
                "I. Organización del Estado",
            ),
            (2, "Derechos y deberes fundamentales de los españoles", "I. Organización del Estado"),
            (
                3,
                "La Corona. Las Cortes Generales: composición y funciones",
                "I. Organización del Estado",
            ),
            (
                4,
                "El Gobierno y la Administración. La Administración General del Estado",
                "I. Organización del Estado",
            ),
            (
                5,
                "La organización territorial del Estado: las Comunidades Autónomas",
                "I. Organización del Estado",
            ),
            (
                6,
                "La Unión Europea: instituciones y derecho de la Unión",
                "I. Organización del Estado",
            ),
            (
                7,
                "Las Leyes del Procedimiento Administrativo Común y del Régimen Jurídico del Sector Público",
                "II. Actividad administrativa",
            ),
            (
                8,
                "El acto administrativo. La revisión de los actos en vía administrativa",
                "II. Actividad administrativa",
            ),
            (
                9,
                "El personal funcionario al servicio de las Administraciones públicas",
                "II. Actividad administrativa",
            ),
            (
                10,
                "Derechos y deberes de los funcionarios. Régimen disciplinario",
                "II. Actividad administrativa",
            ),
            (
                11,
                "El presupuesto del Estado: concepto y estructura",
                "II. Actividad administrativa",
            ),
            (
                12,
                "Políticas de igualdad de género y contra la violencia de género. Discapacidad y dependencia",
                "II. Actividad administrativa",
            ),
            (
                13,
                "Atención al público y atención a la ciudadanía. Los servicios de información administrativa",
                "III. Ofimática",
            ),
            (14, "Administración electrónica y servicios al ciudadano", "III. Ofimática"),
            (
                15,
                "Informática básica: conceptos fundamentales sobre el hardware y el software",
                "III. Ofimática",
            ),
            (16, "Sistemas operativos: Windows. Trabajo en entorno de red", "III. Ofimática"),
            (
                17,
                "Procesadores de texto: Word. Principales funciones y utilidades",
                "III. Ofimática",
            ),
            (18, "Hojas de cálculo: Excel. Principales funciones y utilidades", "III. Ofimática"),
            (19, "Correo electrónico: conceptos elementales y funcionamiento", "III. Ofimática"),
            (20, "La red Internet: navegación, búsquedas y seguridad", "III. Ofimática"),
        ],
    },
    {
        "nombre": "Administrativo",
        "cuerpo": "Cuerpo General Administrativo de la Administración del Estado",
        "grupo": "C1",
        "titulacion": BACH,
        "organismo": "Ministerio de Hacienda y Función Pública",
        "featured": True,
        "order": 2,
        "descripcion": (
            "Tareas administrativas de trámite y colaboración: gestión de "
            "expedientes, contabilidad y apoyo a la gestión pública."
        ),
        "convocatorias": [
            {
                "anio": 2026,
                "referencia_boe": "BOE-A-2026-1103",
                "plazas": 1215,
                "fecha_publicacion": date(2026, 2, 3),
                "fecha_limite": date(2026, 11, 2),
                "estado": "abierta",
            },
        ],
        "temas": [
            (
                1,
                "La Constitución Española de 1978: estructura y contenido",
                "I. Organización pública",
            ),
            (2, "Las Cortes Generales. El Tribunal Constitucional", "I. Organización pública"),
            (
                3,
                "El Gobierno. La Administración General del Estado y sus organismos",
                "I. Organización pública",
            ),
            (
                4,
                "El procedimiento administrativo común de las Administraciones públicas",
                "II. Derecho administrativo",
            ),
            (5, "Los contratos del sector público", "II. Derecho administrativo"),
            (6, "El presupuesto: elaboración, ejecución y control", "III. Gestión financiera"),
        ],
    },
    {
        "nombre": "Gestión de la Administración Civil del Estado",
        "cuerpo": "Cuerpo de Gestión de la Administración Civil del Estado",
        "grupo": "A2",
        "titulacion": DIPL,
        "organismo": "Ministerio de Hacienda y Función Pública",
        "featured": True,
        "order": 3,
        "descripcion": (
            "Funciones de gestión administrativa de nivel intermedio en los "
            "ministerios y organismos de la Administración General del Estado."
        ),
        "convocatorias": [
            {
                "anio": 2025,
                "referencia_boe": "BOE-A-2025-14001",
                "plazas": 560,
                "fecha_publicacion": date(2025, 7, 10),
                "fecha_limite": date(2025, 8, 7),
                "estado": "en_proceso",
            },
        ],
        "temas": [
            (1, "El Estado social y democrático de Derecho", "I. Derecho constitucional"),
            (2, "La organización administrativa: principios", "II. Derecho administrativo"),
            (3, "Las fuentes del Derecho administrativo", "II. Derecho administrativo"),
        ],
    },
    {
        "nombre": "Superior de Administradores Civiles del Estado",
        "cuerpo": "Cuerpo Superior de Administradores Civiles del Estado",
        "grupo": "A1",
        "titulacion": GRADO,
        "organismo": "Ministerio de Hacienda y Función Pública",
        "featured": False,
        "order": 20,
        "descripcion": (
            "El cuerpo directivo generalista de la Administración General del "
            "Estado: diseño y evaluación de políticas públicas."
        ),
        "convocatorias": [
            {
                "anio": 2025,
                "referencia_boe": "BOE-A-2025-15200",
                "plazas": 110,
                "fecha_publicacion": date(2025, 9, 2),
                "fecha_limite": date(2025, 9, 30),
                "estado": "en_proceso",
            },
        ],
        "temas": [],
    },
    {
        "nombre": "Tramitación Procesal y Administrativa",
        "cuerpo": "Cuerpo de Tramitación Procesal y Administrativa",
        "grupo": "C1",
        "titulacion": BACH,
        "organismo": "Ministerio de la Presidencia, Justicia y Relaciones con las Cortes",
        "featured": True,
        "order": 4,
        "descripcion": (
            "Tramitación de procedimientos judiciales: registro, actos de "
            "comunicación y apoyo a jueces y letrados de la Administración de "
            "Justicia."
        ),
        "convocatorias": [
            {
                "anio": 2026,
                "referencia_boe": "BOE-A-2026-2210",
                "plazas": 1508,
                "fecha_publicacion": date(2026, 3, 2),
                "fecha_limite": date(2026, 10, 1),
                "estado": "abierta",
            },
        ],
        "temas": [
            (1, "La Constitución Española de 1978. El Poder Judicial", "Bloque único"),
            (2, "La organización judicial española", "Bloque único"),
            (3, "El Letrado de la Administración de Justicia", "Bloque único"),
        ],
    },
    {
        "nombre": "Auxilio Judicial",
        "cuerpo": "Cuerpo de Auxilio Judicial",
        "grupo": "C2",
        "titulacion": ESO,
        "organismo": "Ministerio de la Presidencia, Justicia y Relaciones con las Cortes",
        "featured": True,
        "order": 5,
        "descripcion": (
            "Funciones de auxilio en juzgados y tribunales: actos de "
            "comunicación, archivo y mantenimiento del orden en las vistas."
        ),
        "convocatorias": [
            {
                "anio": 2025,
                "referencia_boe": "BOE-A-2025-8802",
                "plazas": 826,
                "fecha_publicacion": date(2025, 4, 22),
                "fecha_limite": date(2025, 5, 20),
                "estado": "resuelta",
            },
        ],
        "temas": [],
    },
    {
        "nombre": "Gestión Procesal y Administrativa",
        "cuerpo": "Cuerpo de Gestión Procesal y Administrativa",
        "grupo": "A2",
        "titulacion": DIPL,
        "organismo": "Ministerio de la Presidencia, Justicia y Relaciones con las Cortes",
        "featured": False,
        "order": 21,
        "descripcion": "Gestión de la tramitación procesal en la Administración de Justicia.",
        "convocatorias": [],
        "temas": [],
    },
    {
        "nombre": "Agentes de la Hacienda Pública",
        "cuerpo": "Cuerpo de Agentes del Servicio de Vigilancia Aduanera y Agentes de la Hacienda Pública",
        "grupo": "C2",
        "titulacion": ESO,
        "organismo": "Agencia Estatal de Administración Tributaria",
        "featured": True,
        "order": 6,
        "descripcion": (
            "Apoyo a la gestión, inspección y recaudación tributaria en la Agencia Tributaria."
        ),
        "convocatorias": [
            {
                "anio": 2026,
                "referencia_boe": "BOE-A-2026-3300",
                "plazas": 430,
                "fecha_publicacion": date(2026, 2, 17),
                "fecha_limite": date(2026, 9, 18),
                "estado": "abierta",
            },
        ],
        "temas": [],
    },
    {
        "nombre": "Técnicos de Hacienda",
        "cuerpo": "Cuerpo Técnico de Hacienda",
        "grupo": "A2",
        "titulacion": DIPL,
        "organismo": "Agencia Estatal de Administración Tributaria",
        "featured": False,
        "order": 22,
        "descripcion": "Gestión e inspección tributaria de nivel técnico en la AEAT.",
        "convocatorias": [],
        "temas": [],
    },
    {
        "nombre": "Inspectores de Hacienda del Estado",
        "cuerpo": "Cuerpo Superior de Inspectores de Hacienda del Estado",
        "grupo": "A1",
        "titulacion": GRADO,
        "organismo": "Agencia Estatal de Administración Tributaria",
        "featured": False,
        "order": 23,
        "descripcion": "Inspección financiera y tributaria del Estado.",
        "convocatorias": [],
        "temas": [],
    },
    {
        "nombre": "Policía Nacional (Escala Básica)",
        "cuerpo": "Cuerpo Nacional de Policía, Escala Básica",
        "grupo": "C1",
        "titulacion": BACH,
        "organismo": "Ministerio del Interior — Dirección General de la Policía",
        "featured": True,
        "order": 7,
        "descripcion": (
            "Acceso a la Escala Básica del Cuerpo Nacional de Policía: "
            "seguridad ciudadana e investigación."
        ),
        "convocatorias": [
            {
                "anio": 2026,
                "referencia_boe": "BOE-A-2026-4501",
                "plazas": 2600,
                "fecha_publicacion": date(2026, 4, 6),
                "fecha_limite": date(2026, 10, 30),
                "estado": "abierta",
            },
        ],
        "temas": [],
    },
    {
        "nombre": "Guardia Civil (Cabos y Guardias)",
        "cuerpo": "Escala de Cabos y Guardias de la Guardia Civil",
        "grupo": "C1",
        "titulacion": BACH,
        "organismo": "Ministerio del Interior — Dirección General de la Guardia Civil",
        "featured": False,
        "order": 24,
        "descripcion": "Ingreso en la Escala de Cabos y Guardias de la Guardia Civil.",
        "convocatorias": [],
        "temas": [],
    },
    {
        "nombre": "Ayudantes de Instituciones Penitenciarias",
        "cuerpo": "Cuerpo de Ayudantes de Instituciones Penitenciarias",
        "grupo": "C1",
        "titulacion": BACH,
        "organismo": "Ministerio del Interior — Secretaría General de Instituciones Penitenciarias",
        "featured": False,
        "order": 25,
        "descripcion": "Vigilancia y tratamiento en centros penitenciarios.",
        "convocatorias": [
            {
                "anio": 2025,
                "referencia_boe": "BOE-A-2025-11020",
                "plazas": 900,
                "fecha_publicacion": date(2025, 6, 3),
                "fecha_limite": date(2025, 7, 1),
                "estado": "en_proceso",
            },
        ],
        "temas": [],
    },
    {
        "nombre": "Técnico Auxiliar de Informática",
        "cuerpo": "Cuerpo de Técnicos Auxiliares de Informática de la Administración del Estado",
        "grupo": "C1",
        "titulacion": BACH,
        "organismo": "Ministerio para la Transformación Digital y de la Función Pública",
        "featured": True,
        "order": 8,
        "descripcion": (
            "Operación y soporte de sistemas informáticos en la Administración General del Estado."
        ),
        "convocatorias": [
            {
                "anio": 2026,
                "referencia_boe": "BOE-A-2026-5602",
                "plazas": 390,
                "fecha_publicacion": date(2026, 1, 27),
                "fecha_limite": date(2026, 9, 25),
                "estado": "abierta",
            },
        ],
        "temas": [],
    },
    {
        "nombre": "Gestión de Sistemas e Informática",
        "cuerpo": "Cuerpo de Gestión de Sistemas e Informática de la Administración del Estado",
        "grupo": "A2",
        "titulacion": DIPL,
        "organismo": "Ministerio para la Transformación Digital y de la Función Pública",
        "featured": False,
        "order": 26,
        "descripcion": "Análisis, desarrollo y administración de sistemas de información.",
        "convocatorias": [],
        "temas": [],
    },
    {
        "nombre": "Administrativo de la Seguridad Social",
        "cuerpo": "Cuerpo Administrativo de la Administración de la Seguridad Social",
        "grupo": "C1",
        "titulacion": BACH,
        "organismo": "Ministerio de Inclusión, Seguridad Social y Migraciones",
        "featured": False,
        "order": 27,
        "descripcion": "Gestión administrativa en las entidades de la Seguridad Social.",
        "convocatorias": [],
        "temas": [],
    },
    {
        "nombre": "Subinspección Laboral (Empleo y Seguridad Social)",
        "cuerpo": "Cuerpo de Subinspectores Laborales",
        "grupo": "A2",
        "titulacion": DIPL,
        "organismo": "Ministerio de Trabajo y Economía Social",
        "featured": False,
        "order": 28,
        "descripcion": "Apoyo a la Inspección de Trabajo y Seguridad Social.",
        "convocatorias": [],
        "temas": [],
    },
]


class Command(BaseCommand):
    help = "Seed real state-level oposiciones with convocatorias and temarios."

    def handle(self, *args: Any, **options: Any) -> None:
        created_count = 0
        for entry in SEED:
            oposicion, created = Oposicion.objects.update_or_create(
                nombre=entry["nombre"],
                ambito=Oposicion.Ambito.ESTADO,
                defaults={
                    "cuerpo": entry["cuerpo"],
                    "grupo": entry["grupo"],
                    "titulacion_requerida": entry["titulacion"],
                    "organismo_convocante": entry["organismo"],
                    "descripcion": entry["descripcion"],
                    "sistema_selectivo": Oposicion.SistemaSelectivo.OPOSICION,
                    "is_featured": entry["featured"],
                    "homepage_order": entry["order"],
                    "is_published": True,
                },
            )
            created_count += int(created)
            for conv in entry["convocatorias"]:
                Convocatoria.objects.update_or_create(
                    oposicion=oposicion,
                    anio=conv["anio"],
                    defaults={
                        "referencia_boe": conv.get("referencia_boe", ""),
                        "url_boe": (
                            f"https://www.boe.es/diario_boe/txt.php?id={conv['referencia_boe']}"
                            if conv.get("referencia_boe")
                            else ""
                        ),
                        "plazas": conv.get("plazas"),
                        "plazas_libre": conv.get("plazas_libre"),
                        "plazas_discapacidad": conv.get("plazas_discapacidad"),
                        "fecha_publicacion": conv.get("fecha_publicacion"),
                        "fecha_limite_solicitud": conv.get("fecha_limite"),
                        "estado": conv["estado"],
                    },
                )
            for numero, titulo, bloque in entry["temas"]:
                Tema.objects.update_or_create(
                    oposicion=oposicion,
                    numero=numero,
                    defaults={"titulo": titulo, "bloque": bloque},
                )
        total = Oposicion.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(SEED)} oposiciones ({created_count} new, {total} total)."
            )
        )
