#!/usr/bin/env python3
"""Garde-fou : refuse tout envoi qui contiendrait des données personnelles ou commerciales réelles.

Lancé avant chaque commit (hook git) et à chaque push (GitHub Actions). Bloque :
- les fichiers de données (.pdf, .xlsx, .zip, .sqlite, .eml, .jsonl...) ;
- toute adresse mail hors domaines fictifs réservés (example.com, example.org) ;
- tout numéro de téléphone français, IBAN ou numéro SIREN/SIRET écrit en clair ;
- les jetons d'accès (fichiers token.json / credentials.json, clés d'API).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_EXT = {".pst", ".ost", ".eml", ".msg", ".mbox", ".pdf", ".doc", ".docx", ".odt", ".xls", ".xlsx",
                 ".ods", ".csv", ".tsv", ".zip", ".sqlite", ".db", ".jsonl"}
FORBIDDEN_NAMES = {"token.json", "credentials.json", "client_secret.json", ".env"}
ALLOWED_DOMAINS = ("example.com", "example.org", "users.noreply.github.com", "anthropic.com", "googleapis.com")
EMAIL_RE = re.compile(r"[\w.+\-]+@([\w\-]+\.[\w.\-]+)")
PHONE_RE = re.compile(r"(?:(?:\+|00)33\s?[1-9]|\b0[1-9])(?:[\s.\-]?\d{2}){4}\b")
IBAN_RE = re.compile(r"\bFR\d{2}(?:\s?[0-9A-Z]{4}){5}", re.I)
SIREN_RE = re.compile(r"\b(?:SIREN|SIRET)\s*:?\s*(?!0{9})\d{3}\s?\d{3}\s?\d{3}", re.I)
KEY_RE = re.compile(r"sk-ant-[\w\-]{20,}|AIza[\w\-]{30,}")
SKIP = {"scripts/check_no_pii.py", "tests/test_units.py"}  # contiennent des motifs fictifs de test


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                         capture_output=True, text=True, check=True).stdout
    return [Path(p) for p in out.splitlines() if p]


def main() -> int:
    problems = []
    for f in tracked_files():
        if f.as_posix() in SKIP or not f.exists():
            continue
        if f.name in FORBIDDEN_NAMES:
            problems.append(f"{f} : fichier d'identifiants")
            continue
        if f.suffix.lower() in FORBIDDEN_EXT:
            problems.append(f"{f} : type de fichier interdit (données)")
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in EMAIL_RE.finditer(line):
                if not m.group(1).lower().endswith(ALLOWED_DOMAINS) and "{" not in m.group(0):
                    problems.append(f"{f}:{n} : adresse mail réelle possible")
            for label, rx in (("téléphone", PHONE_RE), ("IBAN", IBAN_RE), ("SIREN/SIRET", SIREN_RE), ("clé d'API", KEY_RE)):
                if rx.search(line):
                    problems.append(f"{f}:{n} : {label} possible")
    if problems:
        print("ENVOI BLOQUÉ, données personnelles possibles :")
        print("\n".join(f"  - {p}" for p in problems))
        return 1
    print("OK : aucune donnée personnelle détectée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
