"""Le lecteur IA est testé sans réseau : un faux client renvoie une sortie structurée."""

from datetime import date
from types import SimpleNamespace

from branddeals.classify import PARTNERSHIP_SCHEMA, SYSTEM_PROMPT, LLMReader
from branddeals.config import Rules
from branddeals.models import CollabType, Counterparty, Message, Statut, Thread


class FakeClient:
    def __init__(self, payload):
        self.payload, self.calls = payload, []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=self.payload)])


def _cp():
    d = date(2025, 5, 1)
    m = Message("m1", "t1", "a@marque.example.com", ("creatrice@example.com",), d, "Collab", "Bonjour")
    return Counterparty("marque.example.com", [Thread("t1", [m])])


def test_llm_reader_forces_tool_and_maps_output():
    client = FakeClient({"est_partenariat": True, "marque": "Marque", "type": "payée", "statut": "en attente",
                         "montant": 450, "remarque": "Facture envoyée, paiement à confirmer.",
                         "contact_chaleureux": True, "conversations_pertinentes": ["t1"]})
    p = LLMReader(Rules.load(), client=client).read(_cp(), "texte masqué")
    call = client.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "enregistrer_partenariat"}
    assert call["tools"][0]["input_schema"] is PARTNERSHIP_SCHEMA
    assert call["system"] == SYSTEM_PROMPT
    assert (p.type, p.statut, p.montant, p.a_relancer) == (CollabType.PAYEE, Statut.EN_ATTENTE, 450, True)


def test_llm_reader_returns_none_when_not_a_partnership():
    client = FakeClient({"est_partenariat": False, "marque": "X", "type": "mixte", "statut": "inconnu",
                         "remarque": "", "contact_chaleureux": False})
    assert LLMReader(Rules.load(), client=client).read(_cp(), "…") is None


def test_schema_enums_match_domain_model():
    assert set(PARTNERSHIP_SCHEMA["properties"]["type"]["enum"]) == {c.value for c in CollabType}
    assert set(PARTNERSHIP_SCHEMA["properties"]["statut"]["enum"]) == {s.value for s in Statut}
