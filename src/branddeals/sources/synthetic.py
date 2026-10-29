"""Boîte mail 100 % fictive, pour la démonstration et les tests.

Elle reproduit les situations rencontrées sur la vraie boîte : collabs payées avec facture,
produits offerts, prospections restées sans réponse, refus polis, newsletters, messages trop
lourds pour être téléchargés, numéro de facture réutilisé, mails à soi-même.
Toutes les adresses sont en example.com, conformément au garde-fou du dépôt.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from datetime import date, timedelta

from ..models import Message, Thread
from .base import MessageTooLarge, RawAttachment

ME = "creatrice@example.com"

BRANDS = [
    ("lunettes-azur", "Lunettes Azur"), ("biscuits-mamie", "Biscuits de Mamie"), ("parc-aventure", "Parc Aventure"),
    ("cosmetique-douce", "Cosmétique Douce"), ("jouets-bois", "Jouets en Bois"), ("hotel-lagon", "Hôtel du Lagon"),
    ("matelas-nuage", "Matelas Nuage"), ("agence-pixel", "Agence Pixel"), ("box-gourmande", "Box Gourmande"),
    ("chaussures-ptits-pas", "P'tits Pas"), ("cirque-etoile", "Cirque Étoile"), ("musee-sciences", "Musée des Sciences"),
]


def make_pdf(lines: list[str]) -> bytes:
    """Fabrique un PDF minimal mais valide, dont le texte est lisible par pypdf."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream = "BT /F1 11 Tf 50 780 Td 14 TL " + " ".join(f"({esc(line)}) Tj T*" for line in lines) + " ET"
    data = stream.encode("latin-1", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n" + data + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{off:010d} 00000 n \n".encode() for off in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


class SyntheticMailbox:
    """Implémente MailSource sur des données générées, de façon reproductible (graine fixe)."""

    def __init__(self, seed: int = 7, n_noise: int = 40):
        self.rng = random.Random(seed)
        self.threads: dict[str, Thread] = {}
        self.attachments: dict[str, list[RawAttachment]] = {}
        self.too_large: set[str] = set()
        self.labels: dict[str, set[str]] = {}
        self._n = 0
        self._invoice_no = 0
        self._build(n_noise)

    # -- MailSource -------------------------------------------------------------------------
    def search(self, query: str) -> Iterator[str]:
        q = query.lower()
        wants_docs = "facture" in q and "-facture" not in q
        for tid, t in self.threads.items():
            sent = any(m.sender == ME for m in t.messages)
            if "in:sent" in q and not sent:
                continue
            text = " ".join((m.subject + " " + m.body).lower() for m in t.messages)
            has_doc = any(w in text for w in ("facture", "devis", "contrat"))
            if (wants_docs and has_doc) or (not wants_docs and not has_doc and any(
                    w in text for w in ("collab", "partenariat", "brief", "ugc", "campagne", "offert", "tarif"))):
                yield tid

    def get_thread(self, thread_id: str) -> Thread:
        return self.threads[thread_id]

    def get_attachments(self, message_id: str) -> list[RawAttachment]:
        if message_id in self.too_large:
            raise MessageTooLarge(message_id)
        return self.attachments.get(message_id, [])

    def add_label(self, thread_id: str, label: str) -> None:
        self.labels.setdefault(thread_id, set()).add(label)

    # -- génération --------------------------------------------------------------------------
    def _id(self) -> str:
        self._n += 1
        return f"t{self._n:05d}"

    def _thread(self, brand_addr: str, subject: str, turns: list[tuple[str, str, int]], start: date,
                attach: dict[int, list[RawAttachment]] | None = None, big: set[int] | None = None) -> str:
        tid, msgs, d = self._id(), [], start
        for i, (who, body, gap) in enumerate(turns):
            d += timedelta(days=gap)
            sender, to = (ME, brand_addr) if who == "me" else (brand_addr, ME)
            mid = f"{tid}m{i}"
            atts = (attach or {}).get(i, [])
            msgs.append(Message(mid, tid, sender, (to,), d, subject if i == 0 else f"Re: {subject}", body,
                                size_bytes=9_000_000 if big and i in big else 20_000 + sum(len(a.content) for a in atts),
                                attachment_names=tuple(a.filename for a in atts)))
            if atts:
                self.attachments[mid] = atts
            if big and i in big:
                self.too_large.add(mid)
        self.threads[tid] = Thread(tid, msgs)
        return tid

    def _invoice(self, client: str, amount: int, d: date, reuse: str | None = None) -> RawAttachment:
        if reuse is None:
            self._invoice_no += 1
            num = f"{d.year}-{self._invoice_no:03d}"
        else:
            num = reuse
        lines = ["EXEMPLE CRÉATRICE - SIREN 000000000", f"FACTURE N° {num}", f"Date : {d:%d/%m/%Y}",
                 f"Client : {client}", "Prestation : Story + Réel", f"Total TTC : {amount},00 EUR",
                 "TVA non applicable, art. 293 B du CGI"]
        return RawAttachment(f"Facture_{num}.pdf", "application/pdf", make_pdf(lines))

    def _build(self, n_noise: int) -> None:
        rng, base = self.rng, date(2021, 1, 10)
        last_num = None
        for k, (slug, name) in enumerate(BRANDS):
            addr = f"contact@{slug}.example.com"
            start = base + timedelta(days=rng.randint(0, 1700))
            kind = k % 4
            if kind == 0:  # collab payée avec devis, contrat et facture
                amount = rng.choice([150, 250, 400, 800])
                inv_date = start + timedelta(days=40)
                reuse = last_num if k == 8 else None  # piège : numéro de facture réutilisé
                inv = self._invoice(name, amount, inv_date, reuse)
                last_num = inv.filename.removeprefix("Facture_").removesuffix(".pdf")
                contract = RawAttachment("Contrat_collaboration.pdf", "application/pdf",
                                         make_pdf(["CONTRAT DE COLLABORATION", f"Marque : {name}", f"Rémunération : {amount} EUR HT"]))
                self._thread(addr, f"Collaboration {name} x créatrice", [
                    ("them", f"Bonjour, nous aimerions une collaboration rémunérée. Quel est votre tarif ? {name}", 0),
                    ("me", f"Bonjour, avec plaisir ! Mon tarif pour une Story + un Réel est de {amount} EUR.", 2),
                    ("them", "Parfait, voici le contrat à signer.", 3),
                    ("me", "Contrat signé en pièce jointe, merci !", 1),
                    ("me", "Voici ma facture pour la prestation.", 33),
                    ("them", "Merci, paiement effectué.", 10),
                ], start, attach={2: [contract], 4: [inv, RawAttachment("image001.png", "image/png", b"x")]})
            elif kind == 1:  # produit offert, contact chaleureux, ancien : à relancer
                self._thread(addr, f"Partenariat {name}", [
                    ("them", "Bonjour, nous serions ravis de vous offrir notre nouveau produit contre une Story.", 0),
                    ("me", "Avec grand plaisir, merci ! Voici mon adresse.", 1),
                    ("them", "Colis envoyé ! Au plaisir de retravailler ensemble.", 4),
                ], base + timedelta(days=rng.randint(0, 600)))
            elif kind == 2:  # brief de campagne volumineux (trop lourd pour être téléchargé)
                self._thread(addr, f"Brief campagne {name}", [
                    ("them", "Voici le brief de la campagne et les visuels.", 0),
                    ("me", "Merci, c'est noté pour le brief !", 1),
                ], start, attach={0: [RawAttachment("Brief_campagne.pdf", "application/pdf", b"")]}, big={0})
            else:  # prospection envoyée par la créatrice, refus poli
                self._thread(addr, "Demande de collaboration", [
                    ("me", "Bonjour, j'adore votre marque, seriez-vous ouverts à un partenariat ?", 0),
                    ("them", "Merci beaucoup, mais nos partenariats sont complets cette année.", 5),
                ], start)
        for i in range(n_noise):  # bruit : prospections sans réponse, newsletters, mails à soi-même
            d = base + timedelta(days=rng.randint(0, 2000))
            r = i % 3
            if r == 0:
                self._thread(f"hello@hotel-{i}.example.com", "Demande de collaboration",
                             [("me", "Bonjour, seriez-vous ouverts à une collaboration ?", 0)], d)
            elif r == 1:
                self._thread(f"news@boutique-{i}.example.com", "-50 % ce week-end !",
                             [("them", "Profitez de nos promotions, campagne exceptionnelle.", 0)], d)
            else:
                self._thread(ME, "note perso", [("me", "facture électricité à payer", 0)], d)
