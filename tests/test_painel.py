"""Testes da lógica pura do painel de progresso."""
from __future__ import annotations

import json

from preditor.painel import calc_progress


def test_empty_checklist_is_zero():
    r = calc_progress([])
    assert r["overall"] == 0.0
    assert r["n_items"] == 0


def test_all_done_is_one():
    items = [{"id": "a", "fase": "Setup", "peso": 2, "estado": "Feito"}]
    r = calc_progress(items)
    assert r["overall"] == 1.0
    assert r["by_phase"]["Setup"] == 1.0


def test_factors_weighted():
    items = [
        {"id": "a", "fase": "Setup", "peso": 1, "estado": "Feito"},        # 1
        {"id": "b", "fase": "Setup", "peso": 1, "estado": "Em revisao"},   # .75
        {"id": "c", "fase": "Setup", "peso": 1, "estado": "Em andamento"}, # .4
        {"id": "d", "fase": "Setup", "peso": 1, "estado": "Pendente"},     # 0
        {"id": "e", "fase": "Setup", "peso": 1, "estado": "Bloqueado"},    # 0
    ]
    r = calc_progress(items)
    assert abs(r["overall"] - (2.15 / 5)) < 1e-9


def test_blocked_and_pending_zero():
    items = [{"estado": "Bloqueado", "peso": 3}, {"estado": "Pendente", "peso": 2}]
    assert calc_progress(items)["overall"] == 0.0


def test_by_phase():
    items = [
        {"fase": "Setup", "peso": 1, "estado": "Feito"},
        {"fase": "Modelo", "peso": 2, "estado": "Em andamento"},
    ]
    r = calc_progress(items)
    assert r["by_phase"]["Setup"] == 1.0
    assert abs(r["by_phase"]["Modelo"] - 0.4) < 1e-9
    assert "Setup" in r["by_phase"]


def test_accepts_dict_with_items():
    data = {"items": [{"estado": "Feito", "peso": 1, "fase": "Setup"}]}
    assert calc_progress(data)["overall"] == 1.0


def test_accepts_string_json():
    s = json.dumps({"itens": [{"estado": "Feito", "peso": 1, "fase": "Setup"}]})
    assert calc_progress(s)["overall"] == 1.0


def test_accepts_checklist_kw():
    items = [{"estado": "Feito", "peso": 1, "fase": "Setup"}]
    assert calc_progress(checklist=items)["overall"] == 1.0


def test_pt_en_field_aliases():
    it = [{"estado": "Feito", "peso": 2, "fase": "Setup"}]
    it2 = [{"status": "done", "weight": 2, "phase": "Setup"}]
    assert calc_progress(it)["overall"] == calc_progress(it2)["overall"] == 1.0


def test_state_counts():
    items = [{"estado": "Feito"}, {"estado": "Pendente"}]
    r = calc_progress(items)
    assert r["state_counts"]["Feito"] == 1
    assert r["state_counts"]["Pendente"] == 1
