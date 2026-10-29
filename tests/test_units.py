from datetime import date

import pytest

from branddeals.classify import RuleReader, prefilter, transcript
from branddeals.config import Rules
from branddeals.documents import classify_document, keep_attachment, parse_invoice
from branddeals.harvest import batches, counterparty_key, group
from branddeals.models import (
    CollabType,
    Counterparty,
    DocType,
    Document,
    Message,
    Partnership,
    Statut,
    Thread,
)
from branddeals.privacy import mask, pseudonym, strip_quoted
from branddeals.quality import apply_relance_rule, dedupe_invoices, invoice_alerts, months_between
from branddeals.sources.base import RawAttachment
from branddeals.sources.synthetic import make_pdf

ME = "creatrice@example.com"


@pytest.fixture
def rules():
    r = Rules.load()
    r.own_addresses = {ME}
    return r


def msg(i, sender, to, d, body="", atts=()):
    return Message(f"m{i}", "t1", sender, (to,), d, "Sujet", body, 1000, tuple(atts))


# -- regroupement ---------------------------------------------------------------------------------
def test_counterparty_key_domain_vs_freemail(rules):
    assert counterparty_key("anne@marque.example.com", rules) == "marque.example.com"
    assert counterparty_key("Jean.Dupont@gmail.com", rules) == "jean.dupont@gmail.com"
    assert counterparty_key(ME, rules) is None
    assert counterparty_key("noreply@accounts.google.com", rules) is None


def test_group_rejects_self_mails_and_merges_same_brand(rules):
    d = date(2025, 1, 1)
    t1 = Thread("a", [msg(1, ME, "x@marque.example.com", d)])
    t2 = Thread("b", [msg(2, "y@marque.example.com", ME, d)])
    t3 = Thread("c", [msg(3, ME, ME, d)])
    cps, rejected = group({"a": t1, "b": t2, "c": t3}, rules)
    assert [c.key for c in cps] == ["marque.example.com"]
    assert len(cps[0].threads) == 2
    assert [t.id for t in rejected["a_soi_meme"]] == ["c"]


def test_batches():
    assert [len(b) for b in batches(list(range(60)), 25)] == [25, 25, 10]


# -- règles avant lecture -------------------------------------------------------------------------
def test_prefilter_motifs(rules):
    d = date(2025, 1, 1)
    sans_reponse = Counterparty("h.example.com", [Thread("t", [msg(1, ME, "a@h.example.com", d, "collab ?")])])
    assert prefilter(sans_reponse, rules).motif == "sollicitation_sans_reponse"
    refus = Counterparty("h.example.com", [Thread("t", [msg(1, ME, "a@h.example.com", d, "collab ?"),
                                                        msg(2, "a@h.example.com", ME, d, "Nos partenariats sont complets.")])])
    assert prefilter(refus, rules).motif == "refus_poli"


# -- confidentialité ------------------------------------------------------------------------------
def test_mask_removes_personal_data_but_keeps_brand_domain():
    txt = "Appelez-moi au 06 12 34 56 78, IBAN FR76 3000 6000 0112 3456 7890 189, écrivez à anne@marque.fr"
    out = mask(txt)
    assert "06 12" not in out and "FR76" not in out and "anne@" not in out
    assert "[TEL]" in out and "[IBAN]" in out and "***@marque.fr" in out


def test_strip_quoted_removes_history():
    body = "Merci, c'est validé.\n\nLe lun. 3 mars 2025 à 10:00, Anne a écrit :\n> ancien message"
    assert strip_quoted(body) == "Merci, c'est validé."


def test_pseudonym_is_stable_and_not_reversible():
    assert pseudonym("A@x.fr") == pseudonym("a@x.fr ")
    assert "x.fr" not in pseudonym("a@x.fr")


# -- documents ------------------------------------------------------------------------------------
def test_keep_attachment_filters_signature_images(rules):
    assert keep_attachment(RawAttachment("image001.png", "image/png", b""), rules) is False
    assert keep_attachment(RawAttachment("facture mars.jpg", "image/jpeg", b""), rules) is True
    assert keep_attachment(RawAttachment("contrat.pdf", "application/pdf", b""), rules) is True


def test_invoice_parsing_from_generated_pdf(rules):
    from branddeals.documents import pdf_text

    text = pdf_text(make_pdf(["EXEMPLE CRÉATRICE - SIREN 000000000", "FACTURE N° 2026-004",
                              "Date : 16/09/2026", "Total TTC : 1 250,00 EUR"]))
    num, amount, printed = parse_invoice(text)
    assert (num, amount, printed) == ("2026-004", 1250.0, date(2026, 9, 16))
    assert classify_document("Facture.pdf", text, rules) == (DocType.FACTURE_EMISE, True)
    assert classify_document("Facture_fournisseur.pdf", "Facture n° 99", rules)[0] is DocType.FACTURE_RECUE


# -- contrôles ------------------------------------------------------------------------------------
def _inv(num, cp, amount=100.0, d=date(2025, 1, 1)):
    return Document("t", "m", d, cp, "f.pdf", DocType.FACTURE_EMISE, num, amount, True, "x")


def test_reused_invoice_number_is_flagged():
    alerts = invoice_alerts([_inv("12", "a.fr"), _inv("12", "b.fr"), _inv("13", "a.fr")])
    assert [a.sujet for a in alerts] == ["numéro de facture réutilisé"]


def test_same_invoice_sent_twice_counts_once():
    assert len(dedupe_invoices([_inv("12", "a.fr"), _inv("12", "a.fr", d=date(2025, 2, 1))])) == 1


def test_months_between():
    assert months_between(date(2026, 4, 28), date(2026, 10, 27)) == 5
    assert months_between(date(2026, 4, 27), date(2026, 10, 27)) == 6


def test_relance_rule():
    def p(statut, last, warm=False):
        return Partnership("k", "M", None, None, date(2024, 1, 1), last, CollabType.PAYEE, statut, a_relancer=warm)
    today = date(2026, 10, 27)
    old_paid, recent_paid = p(Statut.PAYEE, date(2025, 1, 1)), p(Statut.PAYEE, date(2026, 9, 1))
    old_dropped = p(Statut.ABANDONNEE, date(2024, 1, 1), warm=True)
    apply_relance_rule([old_paid, recent_paid, old_dropped], today, 6)
    assert (old_paid.a_relancer, recent_paid.a_relancer, old_dropped.a_relancer) == (True, False, False)


# -- lecture --------------------------------------------------------------------------------------
def test_transcript_is_masked_and_labels_speakers(rules):
    d = date(2025, 1, 1)
    cp = Counterparty("m.example.com", [Thread("t", [msg(1, "a@m.example.com", ME, d, "Mon numéro : 06 11 22 33 44"),
                                                     msg(2, ME, "a@m.example.com", d, "Mon tarif est de 300 €")])])
    text = transcript(cp, rules.own_addresses)
    assert "MARQUE" in text and "CRÉATRICE" in text and "06 11" not in text
    p = RuleReader(rules).read(cp, text)
    assert p.type is CollabType.PAYEE and p.montant == 300.0
