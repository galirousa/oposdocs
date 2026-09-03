import datetime as dt

import factory

from oposiciones.factories import OposicionFactory

from .models import HarvestedItem, HarvestRule, HarvestRun


class HarvestRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HarvestRule

    oposicion = factory.SubFactory(OposicionFactory)
    terminos = "Auxiliar Administrativo\nCuerpo General Auxiliar"
    is_active = True


class HarvestRunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HarvestRun

    fecha = factory.Sequence(lambda n: dt.date(2026, 9, 1) - dt.timedelta(days=n))
    status = HarvestRun.Status.OK


class HarvestedItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HarvestedItem

    identificador = factory.Sequence(lambda n: f"BOE-A-2026-{10000 + n}")
    fecha_publicacion = dt.date(2026, 9, 1)
    seccion = "II. Autoridades y personal. - B. Oposiciones y concursos"
    departamento = "MINISTERIO DE HACIENDA"
    epigrafe = "Cuerpo General Auxiliar de la Administración del Estado"
    titulo = factory.Sequence(
        lambda n: f"Resolución {n} por la que se convocan pruebas selectivas."
    )
    url_pdf = factory.LazyAttribute(
        lambda o: f"https://www.boe.es/boe/dias/2026/09/01/pdfs/{o.identificador}.pdf"
    )
    url_html = factory.LazyAttribute(
        lambda o: f"https://www.boe.es/diario_boe/txt.php?id={o.identificador}"
    )
    size_bytes = 240000
