"""Ligne de commande.

  branddeals demo --out demo_output            boîte fictive, aucune connexion ni clé d'API
  branddeals run --credentials credentials.json --reader llm --out sortie/
  branddeals views --db sortie/partenariats.sqlite
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import date

from .classify import LLMReader, RuleReader
from .config import Rules
from .pipeline import run


def _cmd_demo(args) -> int:
    from .sources.synthetic import ME, SyntheticMailbox

    rules = Rules.load(args.rules)
    rules.own_addresses = {ME}
    res = run(SyntheticMailbox(seed=args.seed), RuleReader(rules), rules, args.out, today=date(2026, 10, 27))
    print(json.dumps(res.stats, indent=2, ensure_ascii=False))
    print("\nSorties :", json.dumps(res.outputs, indent=2, ensure_ascii=False))
    return 0


def _cmd_run(args) -> int:
    from .sources.gmail_api import GmailSource

    rules = Rules.load(args.rules)
    if args.me:
        rules.own_addresses |= {a.lower() for a in args.me}
    source = GmailSource(args.credentials, args.token, rules.max_message_bytes)
    reader = LLMReader(rules, model=args.model) if args.reader == "llm" else RuleReader(rules)
    res = run(source, reader, rules, args.out, workers=args.workers, apply_labels=not args.no_labels)
    print(json.dumps(res.stats, indent=2, ensure_ascii=False))
    return 0


def _cmd_views(args) -> int:
    con = sqlite3.connect(args.db)
    for view in ("v_a_relancer", "v_factures_en_attente", "v_numeros_factures_reutilises", "v_activite_par_annee"):
        rows = con.execute(f"SELECT * FROM {view}").fetchall()  # noqa: S608 - nom de vue fixe
        print(f"\n== {view} ({len(rows)} lignes)")
        for r in rows[: args.limit]:
            print("  ", r)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(prog="branddeals", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rules", default=None, help="fichier de règles (défaut : config/rules.yaml)")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="traiter une boîte fictive")
    d.add_argument("--out", default="demo_output")
    d.add_argument("--seed", type=int, default=7)
    d.set_defaults(func=_cmd_demo)

    r = sub.add_parser("run", help="traiter une vraie boîte Gmail")
    r.add_argument("--credentials", required=True, help="fichier OAuth client de Google Cloud")
    r.add_argument("--token", default="token.json")
    r.add_argument("--me", nargs="*", help="adresses de la créatrice (en plus de celles du fichier de règles)")
    r.add_argument("--reader", choices=["llm", "rules"], default="llm")
    r.add_argument("--model", default="claude-sonnet-4-5")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--no-labels", action="store_true", help="ne pas poser le libellé Partenariats")
    r.add_argument("--out", default="sortie")
    r.set_defaults(func=_cmd_run)

    v = sub.add_parser("views", help="afficher les vues métier de la base")
    v.add_argument("--db", required=True)
    v.add_argument("--limit", type=int, default=10)
    v.set_defaults(func=_cmd_views)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
