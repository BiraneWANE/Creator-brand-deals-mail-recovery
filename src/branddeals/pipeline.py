"""Chef d'orchestre : enchaîne les étapes et produit la base SQLite, le classeur et un rapport chiffré."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import documents, harvest, quality, report, store
from .classify import Prefilter, Reader, prefilter, transcript
from .config import Rules
from .models import Counterparty, Partnership
from .sources.base import MailSource

log = logging.getLogger("branddeals")
LABEL = "Partenariats"


@dataclass
class RunResult:
    stats: dict[str, int] = field(default_factory=dict)
    partnerships: list[Partnership] = field(default_factory=list)
    alerts: list = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)


def _read_batch(batch: list[Counterparty], reader: Reader, rules: Rules) -> list[Partnership]:
    out = []
    for cp in batch:
        p = reader.read(cp, transcript(cp, rules.own_addresses))
        if p:
            out.append(p)
    return out


def run(source: MailSource, reader: Reader, rules: Rules, out_dir: str | Path, today: date | None = None,
        workers: int = 4, batch_size: int = 25, apply_labels: bool = True) -> RunResult:
    out_dir, today = Path(out_dir), today or date.today()
    out_dir.mkdir(parents=True, exist_ok=True)
    res = RunResult()

    # 1-2. Récolte et regroupement : aucun appel coûteux
    threads = harvest.harvest(source, rules)
    cps, rejected = harvest.group(threads, rules)
    log.info("%d conversations, %d interlocuteurs", len(threads), len(cps))

    # 3a. Règles gratuites
    decisions: dict[str, Prefilter] = {cp.key: prefilter(cp, rules) for cp in cps}
    to_read = [cp for cp in cps if decisions[cp.key].keep]

    # 3b. Lecture, par lots en parallèle (le lecteur peut être un modèle de langage)
    partnerships: list[Partnership] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for found in pool.map(lambda b: _read_batch(b, reader, rules), harvest.batches(to_read, batch_size)):
            partnerships.extend(found)

    # 4. Libellé Gmail sur les conversations retenues : la seule écriture dans la boîte
    labelled: set[str] = set()
    if apply_labels:
        for p in partnerships:
            for tid in p.thread_ids:
                source.add_label(tid, LABEL)
                labelled.add(tid)

    # 5. Documents, contrôles, relances
    by_key = {cp.key: cp for cp in cps}
    docs = quality.dedupe_invoices(documents.extract_documents(source, partnerships, by_key, rules, out_dir / "documents"))
    quality.link_invoice_numbers(partnerships, docs)
    quality.apply_relance_rule(partnerships, today, rules.relance_months)
    alerts = quality.invoice_alerts(docs)

    # 6. Sorties
    res.stats = {
        "conversations_candidates": len(threads),
        "conversations_ecartees_avant_lecture": sum(len(v) for v in rejected.values()),
        "interlocuteurs_examines": len(cps),
        "interlocuteurs_ecartes_par_regles": len(cps) - len(to_read),
        "interlocuteurs_lus": len(to_read),
        "partenariats_retenus": len(partnerships),
        "a_relancer": sum(p.a_relancer for p in partnerships),
        "conversations_libellees": len(labelled),
        "documents_extraits": sum(1 for d in docs if d.path),
        "documents_a_recuperer_a_la_main": sum(1 for d in docs if d.path is None),
        "alertes": len(alerts),
    }
    con = store.connect(out_dir / "partenariats.sqlite")
    store.save(con, cps, decisions, partnerships, docs, rules.freemail_domains, labelled)
    con.close()
    xlsx = report.write_workbook(out_dir / "Partenariats.xlsx", partnerships, docs, alerts,
                                 {k: v for k, v in res.stats.items() if k.startswith(("documents", "conversations_lib"))})
    (out_dir / "rapport.json").write_text(json.dumps(res.stats, indent=2, ensure_ascii=False), encoding="utf-8")
    res.partnerships, res.alerts = partnerships, alerts
    res.outputs = {"base": str(out_dir / "partenariats.sqlite"), "classeur": str(xlsx), "rapport": str(out_dir / "rapport.json")}
    return res
