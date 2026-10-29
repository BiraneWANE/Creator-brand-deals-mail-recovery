"""Étape 5 : contrôles de cohérence et règle de relance.

Les contrôles ne corrigent rien : ils signalent, avec un motif lisible, ce qu'un humain doit regarder.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .models import DocType, Document, Partnership, Statut


@dataclass(frozen=True)
class Alerte:
    niveau: str  # « important » ou « à vérifier »
    sujet: str
    detail: str


def dedupe_invoices(docs: list[Document]) -> list[Document]:
    """Une même facture renvoyée deux fois (relance, version corrigée) ne compte qu'une fois."""
    seen, out = set(), []
    for d in sorted(docs, key=lambda d: d.sent_at):
        if d.doc_type is not DocType.FACTURE_EMISE:
            out.append(d)
            continue
        key = (d.numero, d.counterparty_key, d.montant)
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def invoice_alerts(docs: list[Document]) -> list[Alerte]:
    """Un numéro de facture doit être unique : le même numéro pour deux clients différents est signalé."""
    by_num: dict[str, set[str]] = defaultdict(set)
    for d in docs:
        if d.doc_type is DocType.FACTURE_EMISE and d.numero:
            by_num[d.numero].add(d.counterparty_key)
    alerts = [Alerte("important", "numéro de facture réutilisé", f"n° {n} utilisé pour {len(c)} clients différents")
              for n, c in sorted(by_num.items()) if len(c) > 1]
    alerts += [Alerte("à vérifier", "date de facture", f"{d.filename} : {d.remarque}")
               for d in docs if d.remarque.startswith("Date imprimée")]
    alerts += [Alerte("à vérifier", "document non téléchargé", f"{d.counterparty_key} : {d.filename}")
               for d in docs if d.path is None]
    return alerts


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month) - (b.day < a.day)


def apply_relance_rule(partnerships: list[Partnership], today: date, months: int = 6) -> None:
    """À relancer = collab réussie ou contact chaleureux, ET aucun échange depuis plus de N mois.

    La règle est appliquée de façon uniforme ici, plutôt que laissée à l'appréciation du lecteur :
    deux lectures différentes ne doivent pas produire deux politiques de relance différentes.
    """
    for p in partnerships:
        reussie = p.statut is Statut.PAYEE or (p.statut is Statut.NON_FACTUREE and p.type.value != "payée")
        dormant = months_between(p.dernier_echange, today) >= months
        p.a_relancer = dormant and p.statut is not Statut.ABANDONNEE and (p.a_relancer or reussie)


def link_invoice_numbers(partnerships: list[Partnership], docs: list[Document]) -> None:
    """Reporte sur chaque partenariat les numéros des factures retrouvées dans ses pièces jointes."""
    by_cp: dict[str, set[str]] = defaultdict(set)
    for d in docs:
        if d.doc_type is DocType.FACTURE_EMISE and d.numero:
            by_cp[d.counterparty_key].add(d.numero)
    for p in partnerships:
        if not p.facture and by_cp.get(p.counterparty_key):
            p.facture = ", ".join(sorted(by_cp[p.counterparty_key]))
