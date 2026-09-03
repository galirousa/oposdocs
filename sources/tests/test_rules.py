"""Rule matching: accent- and case-insensitive, optionally narrowed by organism."""

import pytest

from oposiciones.factories import OposicionFactory
from sources.factories import HarvestedItemFactory, HarvestRuleFactory
from sources.models import normalize

pytestmark = pytest.mark.django_db


class TestNormalize:
    def test_strips_accents_and_case(self):
        assert normalize("Oposición Técnica") == "oposicion tecnica"


class TestHarvestRule:
    def test_matches_ignoring_case_and_accents(self):
        rule = HarvestRuleFactory(terminos="Gestión Procesal")
        assert rule.matches("Cuerpo de GESTION PROCESAL y Administrativa", "MINISTERIO")

    def test_requires_one_of_the_terms(self):
        rule = HarvestRuleFactory(terminos="Gestión Procesal\nTramitación")
        assert rule.matches("Cuerpo de Tramitación Procesal", "MINISTERIO")
        assert not rule.matches("Cuerpo de Auxilio Judicial", "MINISTERIO")

    def test_departamento_filter_narrows(self):
        rule = HarvestRuleFactory(
            terminos="Auxiliar", departamento_contiene="Ministerio de Hacienda"
        )
        assert rule.matches("Cuerpo Auxiliar", "MINISTERIO DE HACIENDA")
        assert not rule.matches("Cuerpo Auxiliar", "AYUNTAMIENTO DE VIGO")

    def test_inactive_rule_never_matches(self):
        rule = HarvestRuleFactory(terminos="Auxiliar", is_active=False)
        assert not rule.matches("Cuerpo Auxiliar", "MINISTERIO")

    def test_blank_lines_are_not_wildcard_terms(self):
        """An empty line would otherwise match every title ever published."""
        rule = HarvestRuleFactory(terminos="Auxiliar\n\n   \n")
        assert rule.term_list() == ["Auxiliar"]
        assert not rule.matches("Cuerpo Superior de Inspectores", "MINISTERIO")


class TestItemMatching:
    def test_matching_rules_finds_the_oposicion(self):
        oposicion = OposicionFactory(nombre="Gestión Procesal")
        HarvestRuleFactory(oposicion=oposicion, terminos="Gestión Procesal")
        HarvestRuleFactory(terminos="Bombero")
        item = HarvestedItemFactory(
            titulo="Resolución por la que se convocan pruebas para Gestión Procesal."
        )
        assert [rule.oposicion for rule in item.matching_rules()] == [oposicion]
