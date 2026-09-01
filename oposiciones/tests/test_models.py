import pytest
from django.core.exceptions import ValidationError

from oposiciones.factories import ConvocatoriaFactory, OposicionFactory, TemaFactory
from oposiciones.models import Oposicion

pytestmark = pytest.mark.django_db


class TestSlug:
    def test_auto_generated_from_nombre(self):
        op = OposicionFactory(nombre="Auxiliar Administrativo")
        assert op.slug == "auxiliar-administrativo"

    def test_transliterates_accents(self):
        op = OposicionFactory(nombre="Gestión Procesal")
        assert op.slug == "gestion-procesal"

    def test_collision_gets_disambiguated(self):
        first = OposicionFactory(nombre="Administrativo", ambito="estado")
        second = OposicionFactory(nombre="Administrativo", ambito="autonomica", comunidad="galicia")
        assert first.slug == "administrativo"
        assert second.slug != first.slug
        assert second.slug.startswith("administrativo")

    def test_immutable_once_published_via_clean(self):
        op = OposicionFactory(is_published=True)
        op.slug = "otro-slug"
        with pytest.raises(ValidationError):
            op.full_clean()

    def test_programmatic_change_is_reverted_on_save(self):
        op = OposicionFactory(is_published=True)
        original = op.slug
        op.slug = "otro-slug"
        op.save()
        op.refresh_from_db()
        assert op.slug == original

    def test_mutable_while_unpublished(self):
        op = OposicionFactory(is_published=False)
        op.slug = "nuevo-slug"
        op.save()
        op.refresh_from_db()
        assert op.slug == "nuevo-slug"


class TestDerivedTitle:
    def test_estado_appends_del_estado(self):
        op = OposicionFactory(nombre="Auxiliar Administrativo", ambito="estado")
        assert op.derived_title == "Auxiliar Administrativo del Estado"

    def test_no_duplicate_estado(self):
        op = OposicionFactory(
            nombre="Superior de Administradores Civiles del Estado", ambito="estado"
        )
        assert op.derived_title == "Superior de Administradores Civiles del Estado"

    def test_autonomica_appends_comunidad(self):
        op = OposicionFactory(
            nombre="Auxiliar Administrativo",
            ambito=Oposicion.Ambito.AUTONOMICA,
            comunidad="galicia",
        )
        assert "Galicia" in op.derived_title


class TestAnswerParagraph:
    def test_contains_core_facts(self):
        op = OposicionFactory(nombre="Auxiliar Administrativo", grupo="C2")
        ConvocatoriaFactory(oposicion=op, anio=2026, plazas=2856, estado="abierta")
        text = op.answer_paragraph
        assert "Auxiliar Administrativo del Estado" in text
        assert "C2" in text
        assert "2856 plazas" in text or "2.856" in text


class TestTema:
    def test_unique_numero_per_oposicion(self):
        op = OposicionFactory()
        TemaFactory(oposicion=op, numero=1)
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            TemaFactory(oposicion=op, numero=1)
