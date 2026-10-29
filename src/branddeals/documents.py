"""Étape 4 : extraction des documents commerciaux (contrats, devis, factures, briefs).

On ne télécharge pas tout : seuls les messages qui portent un document utile sont ouverts,
repérés à leur liste de pièces jointes et à leur taille. Les logos de signature sont ignorés.
Les messages trop lourds pour l'API ne bloquent pas le traitement : ils sont listés
pour une récupération manuelle, avec le lien vers le mail.
"""

from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path

from .config import Rules
from .models import Counterparty, DocType, Document, Partnership
from .sources.base import MailSource, MessageTooLarge, RawAttachment

TYPE_PATTERNS = [
    (DocType.FACTURE_EMISE, re.compile(r"\b(facture|invoice)\b", re.I)),
    (DocType.CONTRAT, re.compile(r"\b(contrat|contract|convention|accord|cession de droits|charte)\b", re.I)),
    (DocType.DEVIS, re.compile(r"\b(devis|quote|quotation)\b", re.I)),
    (DocType.BON_DE_COMMANDE, re.compile(r"\b(bon de commande|purchase order|\bPO\d+)", re.I)),
    (DocType.BRIEF, re.compile(r"\b(brief|guideline|cahier des charges)\b", re.I)),
]
INVOICE_NO_RE = re.compile(r"facture\s*(?:n[°o]\.?|num[ée]ro)?\s*[:#]?\s*([0-9]{2,4}[-/ ]?[0-9A-Z]{1,5})", re.I)
TOTAL_RE = re.compile(r"(?:total|montant)[^\n\d]{0,25}(\d[\d\s.]*[,.]\d{2})", re.I)
DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


def keep_attachment(att: RawAttachment, rules: Rules) -> bool:
    if any(re.search(p, att.filename, re.I) for p in rules.ignore_patterns):
        return False
    if att.mime_type in rules.keep_mime:
        return True
    if att.mime_type.startswith("image/"):
        return any(k in att.filename.lower() for k in rules.image_keywords)
    return False


def pdf_text(content: bytes, max_pages: int = 3) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
    except Exception:  # PDF scanné ou abîmé : le texte sera vide, le document est quand même gardé
        return ""


def classify_document(filename: str, text: str, rules: Rules) -> tuple[DocType, bool]:
    """Type du document et « émis par la créatrice ? » (en-tête de ses propres factures)."""
    head = f"{filename}\n{text[:1500]}"
    issued = any(mk.lower() in text.lower() for mk in rules.issuer_markers)
    for dtype, pat in TYPE_PATTERNS:
        if pat.search(head):
            if dtype is DocType.FACTURE_EMISE and not issued:
                return DocType.FACTURE_RECUE, False
            return dtype, issued
    return DocType.AUTRE, issued


def parse_invoice(text: str) -> tuple[str | None, float | None, date | None]:
    num = m.group(1).strip() if (m := INVOICE_NO_RE.search(text)) else None
    amount = None
    if m := TOTAL_RE.search(text):
        amount = float(m.group(1).replace(" ", "").replace(".", "").replace(",", ".")) if "," in m.group(1) \
            else float(m.group(1).replace(" ", ""))
    printed = None
    if m := DATE_RE.search(text):
        d, mo, y = map(int, m.groups())
        try:
            printed = date(y, mo, d)
        except ValueError:
            printed = None
    return num, amount, printed


def safe_name(s: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", s, flags=re.UNICODE).strip("_")[:120] or "document"


def extract_documents(source: MailSource, partnerships: list[Partnership], cps: dict[str, Counterparty],
                      rules: Rules, out_dir: Path) -> list[Document]:
    """Télécharge et classe les documents des conversations retenues, rangés par interlocuteur."""
    docs: list[Document] = []
    for p in partnerships:
        cp = cps[p.counterparty_key]
        for t in cp.threads:
            if t.id not in p.thread_ids:
                continue
            for m in t.messages:
                if not m.attachment_names:
                    continue
                try:
                    atts = source.get_attachments(m.id)
                except MessageTooLarge:
                    docs.append(Document(t.id, m.id, m.sent_at, cp.key, ", ".join(m.attachment_names), DocType.AUTRE,
                                         path=None, remarque="Message trop lourd : à récupérer à la main"))
                    continue
                for att in atts:
                    if not keep_attachment(att, rules):
                        continue
                    text = pdf_text(att.content) if att.mime_type == "application/pdf" else ""
                    dtype, issued = classify_document(att.filename, text, rules)
                    num = amount = printed = None
                    if dtype is DocType.FACTURE_EMISE:
                        num, amount, printed = parse_invoice(text)
                    folder = out_dir / safe_name(cp.key)
                    folder.mkdir(parents=True, exist_ok=True)
                    path = folder / f"{m.sent_at.isoformat()}_{safe_name(att.filename)}"
                    path.write_bytes(att.content)
                    note = ""
                    if printed and abs((printed - m.sent_at).days) > 60:
                        note = f"Date imprimée ({printed:%d/%m/%Y}) éloignée de la date d'envoi : à vérifier"
                    docs.append(Document(t.id, m.id, m.sent_at, cp.key, att.filename, dtype, num, amount,
                                         issued, str(path), note))
    return docs
