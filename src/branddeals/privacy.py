"""Protection des données avant tout envoi à un modèle de langage et avant tout export public.

Principe : le modèle lit des conversations pour en tirer un sens commercial (collab payée ?
montant ? statut ?). Il n'a besoin ni des téléphones, ni des IBAN, ni des adresses postales.
On les masque donc AVANT l'appel, de façon déterministe.
"""

from __future__ import annotations

import hashlib
import re

EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+")
PHONE_RE = re.compile(r"(?:(?:\+|00)33\s?[1-9]|\b0[1-9])(?:[\s.\-]?\d{2}){4}\b")
IBAN_RE = re.compile(r"\bFR\d{2}(?:\s?[0-9A-Z]{4}){5}\s?[0-9A-Z]{3}\b", re.I)
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
POSTAL_RE = re.compile(r"\b\d{1,4},?\s(?:bis\s|ter\s)?(?:rue|avenue|av\.|boulevard|bd|place|allée|impasse|chemin)\s[^\n,]{2,60}", re.I)


def mask(text: str, keep_domains: bool = True) -> str:
    """Remplace les données personnelles par des jetons neutres.

    keep_domains=True conserve le domaine des adresses (« ***@marque.fr ») : c'est l'information
    utile pour reconnaître une marque, sans exposer la personne.
    """
    text = IBAN_RE.sub("[IBAN]", text)
    text = CARD_RE.sub("[NUMERO]", text)
    text = PHONE_RE.sub("[TEL]", text)
    text = POSTAL_RE.sub("[ADRESSE]", text)
    if keep_domains:
        return EMAIL_RE.sub(lambda m: "***@" + m.group(0).rsplit("@", 1)[1], text)
    return EMAIL_RE.sub("[EMAIL]", text)


def pseudonym(value: str, salt: str = "") -> str:
    """Identifiant stable et non réversible (SHA-256 tronqué), pour les statistiques publiées."""
    return hashlib.sha256((salt + value.lower().strip()).encode()).hexdigest()[:12]


def strip_quoted(body: str) -> str:
    """Retire l'historique cité (« Le … a écrit : », lignes en >) : souvent 90 % du volume d'un long fil."""
    out = []
    for line in body.splitlines():
        if re.match(r"^\s*(Le .{5,80} a écrit|On .{5,80} wrote|De\s?: .+|From: .+)", line):
            break
        if not line.lstrip().startswith(">"):
            out.append(line)
    return "\n".join(out).strip()
