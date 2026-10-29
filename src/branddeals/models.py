"""Objets métier manipulés d'un bout à l'autre du pipeline.

Le vocabulaire est celui de la créatrice : une « collab » est un partenariat avec une marque
ou une agence, qu'il soit payé, en produit offert, en UGC ou lié à un événement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class CollabType(str, Enum):
    PAYEE = "payée"
    PRODUIT_OFFERT = "produit offert"
    UGC = "UGC"
    CAMPAGNE = "campagne"
    EVENEMENT = "événement"
    MIXTE = "mixte"


class Statut(str, Enum):
    PAYEE = "payée"
    EN_ATTENTE = "en attente"
    NON_FACTUREE = "non facturée"
    ABANDONNEE = "abandonnée"
    INCONNU = "inconnu"


class DocType(str, Enum):
    FACTURE_EMISE = "facture_emise"
    FACTURE_RECUE = "facture_recue"
    CONTRAT = "contrat"
    DEVIS = "devis"
    BON_DE_COMMANDE = "bon_de_commande"
    BRIEF = "brief"
    AUTRE = "autre"


@dataclass(frozen=True)
class Message:
    id: str
    thread_id: str
    sender: str
    recipients: tuple[str, ...]
    sent_at: date
    subject: str = ""
    body: str = ""
    size_bytes: int = 0
    attachment_names: tuple[str, ...] = ()


@dataclass
class Thread:
    id: str
    messages: list[Message]
    matched_queries: set[str] = field(default_factory=set)

    @property
    def first_date(self) -> date:
        return min(m.sent_at for m in self.messages)

    @property
    def last_date(self) -> date:
        return max(m.sent_at for m in self.messages)

    @property
    def subject(self) -> str:
        return self.messages[0].subject if self.messages else ""

    def addresses(self) -> set[str]:
        out: set[str] = set()
        for m in self.messages:
            out.add(m.sender.lower())
            out.update(r.lower() for r in m.recipients)
        return out


@dataclass
class Counterparty:
    """Une marque, une agence ou une plateforme : la clé de regroupement des conversations."""

    key: str  # domaine (marque.fr) ou adresse complète pour les messageries grand public
    threads: list[Thread] = field(default_factory=list)

    @property
    def last_date(self) -> date:
        return max(t.last_date for t in self.threads)


@dataclass
class Partnership:
    """Une ligne du tableau final : un partenariat retenu après lecture des conversations."""

    counterparty_key: str
    marque: str
    contact_nom: str | None
    contact_email: str | None
    premier_echange: date
    dernier_echange: date
    type: CollabType
    statut: Statut
    montant: float | None = None
    facture: str | None = None
    remarque: str = ""
    lien: str | None = None
    a_relancer: bool = False
    thread_ids: list[str] = field(default_factory=list)


@dataclass
class Document:
    thread_id: str
    message_id: str
    sent_at: date
    counterparty_key: str
    filename: str
    doc_type: DocType
    numero: str | None = None
    montant: float | None = None
    emis_par_creatrice: bool = False
    path: str | None = None  # None : message trop lourd, à récupérer à la main
    remarque: str = ""
