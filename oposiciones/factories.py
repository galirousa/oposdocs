import factory

from .models import Convocatoria, Oposicion, Tema


class OposicionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Oposicion

    nombre = factory.Sequence(lambda n: f"Cuerpo de Prueba {n}")
    ambito = Oposicion.Ambito.ESTADO
    grupo = Oposicion.Grupo.C2
    sistema_selectivo = Oposicion.SistemaSelectivo.OPOSICION
    organismo_convocante = "Ministerio de Hacienda y Función Pública"
    titulacion_requerida = "Título de Graduado en Educación Secundaria Obligatoria"
    is_published = True


class ConvocatoriaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Convocatoria

    oposicion = factory.SubFactory(OposicionFactory)
    anio = 2026
    estado = Convocatoria.Estado.ABIERTA
    plazas = 1000


class TemaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tema

    oposicion = factory.SubFactory(OposicionFactory)
    numero = factory.Sequence(lambda n: n + 1)
    titulo = factory.Sequence(lambda n: f"La Constitución Española: tema {n + 1}")
