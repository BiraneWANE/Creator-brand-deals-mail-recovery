"""Chargement des règles métier (config/rules.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_RULES = Path(__file__).resolve().parents[2] / "config" / "rules.yaml"


@dataclass
class Rules:
    own_addresses: set[str]
    queries: list[dict[str, str]]
    freemail_domains: set[str]
    noise_domains: set[str]
    keep_mime: set[str]
    image_keywords: list[str]
    ignore_patterns: list[str]
    max_message_bytes: int
    issuer_markers: list[str]
    relance_months: int
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path | None = None) -> Rules:
        raw = yaml.safe_load(Path(path or DEFAULT_RULES).read_text(encoding="utf-8"))
        att = raw.get("attachments", {})
        return cls(
            own_addresses={a.lower() for a in raw.get("own_addresses", [])},
            queries=raw.get("queries", []),
            freemail_domains={d.lower() for d in raw.get("freemail_domains", [])},
            noise_domains={d.lower() for d in raw.get("noise_domains", [])},
            keep_mime=set(att.get("keep_mime", [])),
            image_keywords=[k.lower() for k in att.get("image_keywords", [])],
            ignore_patterns=att.get("ignore_patterns", []),
            max_message_bytes=int(att.get("max_message_bytes", 6_500_000)),
            issuer_markers=raw.get("issuer_markers", []),
            relance_months=int(raw.get("relance", {}).get("months_without_contact", 6)),
        )
