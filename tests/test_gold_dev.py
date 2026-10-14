"""Pipeline (article.snippets + extract) medida contra o split DEV do conjunto de ouro (T06).

So o split dev guia ajustes; o split test e so reportado. Gold e provisorio (decisao 004).
"""
from __future__ import annotations

import json
from pathlib import Path

from preditor import article as A
from preditor.extract import extract

GOLD = Path(__file__).resolve().parents[1] / "data" / "gold" / "messages.jsonl"


def _load(split):
    return [m for m in (json.loads(x) for x in GOLD.read_text().splitlines() if x.strip()) if m["split"] == split]


def _offers(m):
    out = []
    for sn in A.snippets(A.article_text(m["text"])):
        out += extract(sn, first_seen_at=m["observed_at"]).ofertas
    return out


def measure(split):
    r = {"n": 0, "found": 0, "pair": 0, "bonus": 0, "fim": 0, "neg": 0, "fp": 0}
    for m in _load(split):
        offs = _offers(m)
        if m["kind"] != "positive":
            r["neg"] += 1
            r["fp"] += bool(offs)
            continue
        e = m["expected"]["ofertas"][0]
        r["n"] += 1
        if not offs:
            continue
        r["found"] += 1
        b = max(offs, key=lambda o: (o.origem == e["origem"]) + (o.destino == e["destino"]) + (o.bonus_pct == e["bonus_pct"]))
        r["pair"] += (b.origem, b.destino) == (e["origem"], e["destino"])
        r["bonus"] += b.bonus_pct == e["bonus_pct"]
        r["fim"] += b.fim == e["fim"]
    return r


def test_dev_pair_direction_coverage():
    r = measure("dev")
    assert r["pair"] / r["n"] >= 0.95, r


def test_dev_bonus_coverage():
    r = measure("dev")
    assert r["bonus"] / r["n"] >= 0.95, r


def test_dev_fim_coverage():
    r = measure("dev")
    assert r["fim"] / r["n"] >= 0.75, r


def test_dev_no_false_positives_on_distractors():
    r = measure("dev")
    assert r["fp"] == 0, r


def _one(text, obs):
    offs = []
    for sn in A.snippets(A.article_text(text)):
        offs += extract(sn, first_seen_at=obs).ofertas
    assert offs, text
    return offs[0]


def test_form_esta_oferecendo_transferencias_da_livelo():
    o = _one("A Smiles está oferecendo até 100% de bônus nas transferências de pontos da Livelo. "
             "A oferta é válida somente até amanhã (14).", "2023-06-13T12:00:00-03:00")
    assert (o.origem, o.destino, o.bonus_pct, o.fim) == ("livelo", "smiles", 100, "2023-06-14")


def test_form_valida_ate_23h59_de_hoje():
    o = _one("A Smiles está oferecendo até 70% de bônus nas transferências de pontos da Livelo. "
             "A promoção é válida somente até às 23h59 de hoje (11).", "2024-03-11T10:00:00-03:00")
    assert o.fim == "2024-03-11" and o.inicio is None


def test_dev_all_positives_are_found():
    r = measure("dev")
    assert r["found"] == r["n"], r
