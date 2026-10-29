"""Étapes 1 et 2 : récolte des conversations candidates puis regroupement par interlocuteur.

Ce module ne fait aucun appel à un modèle de langage : il réduit la boîte entière à une liste
d'interlocuteurs (marques, agences) avec leurs conversations, à moindre coût et de façon rejouable.
"""

from __future__ import annotations

from collections import defaultdict

from .config import Rules
from .models import Counterparty, Thread
from .sources.base import MailSource


def harvest(source: MailSource, rules: Rules) -> dict[str, Thread]:
    """Lance chaque recherche, page après page, et dédoublonne les conversations trouvées plusieurs fois."""
    threads: dict[str, Thread] = {}
    for q in rules.queries:
        for tid in source.search(q["q"]):
            if tid not in threads:
                threads[tid] = source.get_thread(tid)
            threads[tid].matched_queries.add(q["name"])
    return threads


def counterparty_key(address: str, rules: Rules) -> str | None:
    """Clé d'un interlocuteur : son domaine, ou son adresse complète s'il écrit depuis une messagerie grand public."""
    address = address.lower().strip()
    if "@" not in address or address in rules.own_addresses:
        return None
    domain = address.rsplit("@", 1)[1]
    if domain in rules.noise_domains:
        return None
    return address if domain in rules.freemail_domains else domain


def group(threads: dict[str, Thread], rules: Rules) -> tuple[list[Counterparty], dict[str, list[Thread]]]:
    """Regroupe les conversations par interlocuteur.

    Renvoie aussi les conversations écartées, avec leur motif, pour la traçabilité :
    - « a_soi_meme » : mails que la créatrice s'envoie (notes, photos) ;
    - « hors_perimetre » : uniquement des domaines hors sujet.
    """
    groups: dict[str, list[Thread]] = defaultdict(list)
    rejected: dict[str, list[Thread]] = defaultdict(list)
    for t in threads.values():
        others = sorted(a for a in t.addresses() if a not in rules.own_addresses)
        if not others:
            rejected["a_soi_meme"].append(t)
            continue
        keys = [k for k in (counterparty_key(a, rules) for a in others) if k]
        if not keys:
            rejected["hors_perimetre"].append(t)
            continue
        groups[keys[0]].append(t)
    cps = [Counterparty(k, sorted(v, key=lambda t: t.last_date, reverse=True)) for k, v in groups.items()]
    cps.sort(key=lambda c: c.last_date, reverse=True)
    return cps, dict(rejected)


def batches(items: list, size: int = 25) -> list[list]:
    """Découpe en lots : chaque lot est lu indépendamment (en parallèle sur une vraie boîte)."""
    return [items[i:i + size] for i in range(0, len(items), size)]
