import hashlib

import factory

from oposiciones.factories import OposicionFactory

from .models import Document, ModerationLog, Report


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    title = factory.Sequence(lambda n: f"Tema {n}: La Constitución Española")
    description = "Apuntes de prueba con contenido suficiente para ser indexable."
    source_type = Document.SourceType.EDITORIAL
    visibility = Document.Visibility.PUBLIC
    moderation_status = Document.ModerationStatus.APPROVED
    sha256 = factory.LazyAttributeSequence(
        lambda o, n: hashlib.sha256(f"{o.title}-{n}".encode()).hexdigest()
    )
    mime_type = "application/pdf"
    size_bytes = 1024
    license = "own_work"
    extraction_status = Document.ExtractionStatus.DONE
    extracted_text = "La Constitución Española de 1978 es la norma suprema."

    @factory.post_generation
    def oposiciones(self, create: bool, extracted: object, **kwargs: object) -> None:
        if not create:
            return
        if extracted:
            self.oposiciones.set(extracted)  # type: ignore[arg-type]
        else:
            self.oposiciones.add(OposicionFactory())


class ReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Report

    document = factory.SubFactory(DocumentFactory)
    reason = Report.Reason.COPYRIGHT
    detail = "Este documento reproduce material con derechos de autor."


class ModerationLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ModerationLog

    document = factory.SubFactory(DocumentFactory)
    from_status = "pending"
    to_status = "approved"
