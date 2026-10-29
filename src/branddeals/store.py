"""Chargement des résultats dans la base SQLite (schema.sql)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .classify import Prefilter
from .models import Counterparty, Document, Partnership

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    return con


def save(con: sqlite3.Connection, cps: list[Counterparty], decisions: dict[str, Prefilter],
         partnerships: list[Partnership], docs: list[Document], freemail: set[str], labelled: set[str]) -> None:
    kept = {p.counterparty_key for p in partnerships}
    with con:
        for cp in cps:
            dec = decisions[cp.key]
            decision = "retenu" if cp.key in kept else ("a_lire" if dec.keep else "ecarte")
            motif = dec.motif if not dec.keep else (None if cp.key in kept else "lu_non_retenu")
            con.execute("INSERT OR REPLACE INTO interlocuteur VALUES (?,?,?,?)",
                        (cp.key, int(cp.key.split("@")[-1] in freemail), decision, motif))
            for t in cp.threads:
                con.execute("INSERT OR REPLACE INTO conversation VALUES (?,?,?,?,?,?,?,?)",
                            (t.id, cp.key, t.subject, t.first_date.isoformat(), t.last_date.isoformat(),
                             len(t.messages), ",".join(sorted(t.matched_queries)), int(t.id in labelled)))
        for p in partnerships:
            con.execute("INSERT OR REPLACE INTO partenariat VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (p.counterparty_key, p.marque, p.contact_nom, p.contact_email,
                         p.premier_echange.isoformat(), p.dernier_echange.isoformat(), p.type.value,
                         p.statut.value, p.montant, p.facture, int(p.a_relancer), p.remarque, p.lien))
        con.executemany(
            "INSERT INTO document (id_conversation,id_message,date_envoi,cle_interlocuteur,nom_fichier,type,numero,"
            "montant,emis_par_creatrice,chemin,remarque) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(d.thread_id, d.message_id, d.sent_at.isoformat(), d.counterparty_key, d.filename, d.doc_type.value,
              d.numero, d.montant, int(d.emis_par_creatrice), d.path, d.remarque) for d in docs])
