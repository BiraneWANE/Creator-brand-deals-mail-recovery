"""Étape 3 : lecture des conversations et décision « est-ce un vrai partenariat ? ».

Deux étages, du moins cher au plus cher :
1. des règles déterministes écartent ce qui n'est clairement pas une collab
   (aucune réponse de la marque, newsletter, refus explicite) : gratuit, explicable, rejouable ;
2. un lecteur décide pour le reste et remplit la fiche du partenariat (type, statut, montant,
   remarque de relance). En production c'est un modèle de langage avec une sortie structurée
   imposée (schéma JSON) ; en démonstration, un lecteur à règles qui suit la même interface.

Le lecteur ne voit jamais que du texte masqué (privacy.mask) et débarrassé de l'historique cité.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from .config import Rules
from .models import CollabType, Counterparty, Partnership, Statut
from .privacy import mask, strip_quoted

REFUSAL_RE = re.compile(r"(partenariats? (sont )?complets|ne (sommes|recherchons) pas|pas en mesure|malheureusement|not looking)", re.I)
NEWSLETTER_RE = re.compile(r"(promotions?|-\d{2} ?%|se désinscrire|unsubscribe|newsletter)", re.I)
AMOUNT_RE = re.compile(r"(\d[\d\s]{1,6}(?:[.,]\d{2})?)\s?(?:€|eur\b|euros?)", re.I)


@dataclass
class Prefilter:
    keep: bool
    motif: str


def prefilter(cp: Counterparty, rules: Rules) -> Prefilter:
    """Règles gratuites appliquées avant toute lecture coûteuse."""
    senders = {m.sender for t in cp.threads for m in t.messages}
    brand_spoke = any(s not in rules.own_addresses for s in senders)
    me_spoke = any(s in rules.own_addresses for s in senders)
    text = " ".join(m.body for t in cp.threads for m in t.messages)
    if not brand_spoke:
        return Prefilter(False, "sollicitation_sans_reponse")
    if not me_spoke:
        return Prefilter(False, "newsletter" if NEWSLETTER_RE.search(text) else "message_entrant_sans_suite")
    n_msgs = sum(len(t.messages) for t in cp.threads)
    if n_msgs <= 2 and REFUSAL_RE.search(text):
        return Prefilter(False, "refus_poli")
    return Prefilter(True, "a_lire")


class Reader(Protocol):
    def read(self, cp: Counterparty, transcript: str) -> Partnership | None:
        """Renvoie la fiche du partenariat, ou None si ce n'en est pas un."""


def transcript(cp: Counterparty, own_addresses: set[str], max_chars: int = 30_000) -> str:
    """Texte envoyé au lecteur : conversations dans l'ordre, sans citations, données personnelles masquées."""
    parts = []
    for t in sorted(cp.threads, key=lambda t: t.first_date):
        parts.append(f"### Conversation {t.id} : {t.subject}")
        for m in t.messages:
            who = "CRÉATRICE" if m.sender in own_addresses else "MARQUE"
            pj = f" [PJ : {', '.join(m.attachment_names)}]" if m.attachment_names else ""
            parts.append(f"[{m.sent_at.isoformat()}] {who}{pj} : {strip_quoted(m.body)}")
    return mask("\n".join(parts))[:max_chars]


class RuleReader:
    """Lecteur déterministe : sert à la démonstration hors ligne et de référence pour les tests."""

    def __init__(self, rules: Rules):
        self.rules = rules

    def read(self, cp: Counterparty, transcript_text: str) -> Partnership | None:
        text = transcript_text.lower()
        amounts = [float(a.replace(" ", "").replace(",", ".")) for a in AMOUNT_RE.findall(transcript_text)]
        paid = "paiement effectué" in text or "virement" in text
        if "facture" in text or amounts:
            ctype = CollabType.PAYEE
            statut = Statut.PAYEE if paid else (Statut.EN_ATTENTE if "facture" in text else Statut.NON_FACTUREE)
        elif "brief" in text or "campagne" in text:
            ctype, statut = CollabType.CAMPAGNE, Statut.INCONNU
        elif "offrir" in text or "offert" in text or "colis" in text:
            ctype, statut = CollabType.PRODUIT_OFFERT, Statut.NON_FACTUREE
        else:
            return None
        warm = any(w in text for w in ("au plaisir", "ravis", "merci beaucoup", "retravailler"))
        name = cp.key.split("@")[-1].split(".")[0].replace("-", " ").title()
        email = next((m.sender for t in cp.threads for m in t.messages if m.sender not in self.rules.own_addresses), None)
        return Partnership(
            counterparty_key=cp.key, marque=name, contact_nom=None, contact_email=email,
            premier_echange=min(t.first_date for t in cp.threads), dernier_echange=cp.last_date,
            type=ctype, statut=statut, montant=max(amounts) if amounts else None,
            remarque="Contact chaleureux, propose de retravailler ensemble." if warm else "",
            thread_ids=[t.id for t in cp.threads],
            a_relancer=warm or statut == Statut.PAYEE,
        )


# -- Lecteur par modèle de langage ------------------------------------------------------------

PARTNERSHIP_SCHEMA = {
    "type": "object",
    "properties": {
        "est_partenariat": {"type": "boolean", "description": "Vraie collaboration ou proposition sérieuse échangée dans les deux sens"},
        "marque": {"type": "string"},
        "contact_nom": {"type": ["string", "null"]},
        "type": {"enum": [c.value for c in CollabType]},
        "statut": {"enum": [s.value for s in Statut]},
        "montant": {"type": ["number", "null"], "description": "Montant convenu en euros, null si non confirmé"},
        "facture": {"type": ["string", "null"]},
        "remarque": {"type": "string", "description": "1 à 2 phrases utiles pour une relance"},
        "contact_chaleureux": {"type": "boolean"},
        "conversations_pertinentes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["est_partenariat", "marque", "type", "statut", "remarque", "contact_chaleureux"],
}

SYSTEM_PROMPT = """Tu analyses la correspondance professionnelle d'une créatrice de contenu avec UNE marque ou agence.
Décide s'il s'agit d'un vrai partenariat : collaboration payée, produit offert, UGC, campagne, événement,
ou au moins une proposition sérieuse échangée dans les deux sens. Une sollicitation sans réponse n'en est pas un.
Statut « abandonnée » seulement si des échanges réels ont eu lieu puis se sont arrêtés.
N'invente jamais un montant : mets-le à null s'il n'est pas confirmé dans les échanges.
Le texte a été masqué (jetons [TEL], [IBAN], ***@domaine) : n'essaie pas de reconstituer ces données.
Réponds uniquement via l'outil enregistrer_partenariat."""


class LLMReader:
    """Lecteur par modèle de langage, sortie contrainte par un schéma JSON (appel d'outil forcé).

    Le fournisseur est interchangeable : seule la méthode _call dépend de l'API utilisée.
    """

    def __init__(self, rules: Rules, model: str = "claude-sonnet-4-5", client=None):
        self.rules, self.model = rules, model
        if client is None:  # pragma: no cover - nécessite une clé d'API
            import anthropic
            client = anthropic.Anthropic()
        self.client = client

    def _call(self, transcript_text: str) -> dict:
        resp = self.client.messages.create(
            model=self.model, max_tokens=1024, system=SYSTEM_PROMPT,
            tools=[{"name": "enregistrer_partenariat", "description": "Fiche du partenariat",
                    "input_schema": PARTNERSHIP_SCHEMA}],
            tool_choice={"type": "tool", "name": "enregistrer_partenariat"},
            messages=[{"role": "user", "content": transcript_text}],
        )
        block = next(b for b in resp.content if getattr(b, "type", "") == "tool_use")
        return block.input if isinstance(block.input, dict) else json.loads(block.input)

    def read(self, cp: Counterparty, transcript_text: str) -> Partnership | None:
        out = self._call(transcript_text)
        if not out.get("est_partenariat"):
            return None
        ids = out.get("conversations_pertinentes") or [t.id for t in cp.threads]
        return Partnership(
            counterparty_key=cp.key, marque=out["marque"], contact_nom=out.get("contact_nom"), contact_email=None,
            premier_echange=min(t.first_date for t in cp.threads), dernier_echange=cp.last_date,
            type=CollabType(out["type"]), statut=Statut(out["statut"]), montant=out.get("montant"),
            facture=out.get("facture"), remarque=out.get("remarque", ""), thread_ids=ids,
            a_relancer=bool(out.get("contact_chaleureux")),
        )
