"""T08b ciclo 2: portão campeão × desafiante (itens 1-10 do PR #27)."""
import inspect
from datetime import date, timedelta
from pathlib import Path

import pytest

from preditor import model as M
from preditor.model import (
    C1,
    block_bootstrap_ci,
    build_daily_grade,
    decide_champion,
    evaluate_c1_vs_b1,
    record_decision_report,
)

ROOT = Path(__file__).resolve().parents[1]
KEY = ("livelo", "smiles", "transfer_bonus")


def mk(start, fs=None, o="livelo", d="smiles", tp="transfer_bonus"):
    return {"origin": o, "destination": d, "event_type": tp, "start_at": start,
            "first_seen_at": fs if fs is not None else start}


HIST = [mk(date(2025, m, 10)) for m in range(1, 7)]


def synth(n=52, step=15):
    d0 = date(2023, 1, 1)
    return [mk(d0 + timedelta(days=i * step + (i * 7) % 5)) for i in range(n)]


def fav(**over):
    kw = {
        "champion_metrics": {"brier": 0.20, "log_loss": 0.60},
        "challenger_metrics": {"brier": 0.10, "log_loss": 0.30},
        "bootstrap_ci_brier": {"ci_low": 0.02, "ci_high": 0.08},
        "bootstrap_ci_logloss": {"ci_low": 0.05, "ci_high": 0.2},
        "challenger_calibrated": True,
    }
    kw.update(over)
    return kw


# ---- item 1 ---------------------------------------------------------------
def test_gate_insufficient_campaigns():
    d = decide_champion(**fav(), n_campaigns_by_pair_type={KEY: 3}, data_source="real")
    assert d["promoted"] is False
    assert any("< 25" in r for r in d["reasons"])


def test_gate_synthetic_blocks():
    d = decide_champion(**fav(), n_campaigns_by_pair_type={KEY: 30}, data_source="synthetic")
    assert d["promoted"] is False
    assert any("dados sintéticos" in r for r in d["reasons"])


def test_gate_real_enough_promotes():
    d = decide_champion(**fav(), n_campaigns_by_pair_type={KEY: 30}, data_source="real")
    assert d["promoted"] is True


def test_gate_empty_dict_fails_closed():
    d = decide_champion(**fav(), n_campaigns_by_pair_type={}, data_source="real")
    assert d["promoted"] is False


def test_gate_min_over_all_pair_types():
    other = ("livelo", "azul", "transfer_bonus")
    d = decide_champion(**fav(), n_campaigns_by_pair_type={KEY: 30, other: 24}, data_source="real")
    assert d["promoted"] is False
    assert any("livelo,azul,transfer_bonus=24 < 25" in r for r in d["reasons"])


def test_gate_unknown_kwarg_and_required():
    with pytest.raises(TypeError):
        decide_champion(**fav(), n_campaigns_by_pair_type={KEY: 30}, data_source="real",
                        synthetic=False)
    with pytest.raises(TypeError):
        decide_champion(**fav())


def test_gate_invalid_data_source():
    with pytest.raises(ValueError):
        decide_champion(**fav(), n_campaigns_by_pair_type={KEY: 30}, data_source="maybe")


# ---- item 2 ---------------------------------------------------------------
def test_calibration_fails_closed():
    kw = fav()
    del kw["challenger_calibrated"]
    d = decide_champion(**kw, n_campaigns_by_pair_type={KEY: 30}, data_source="real")
    assert d["promoted"] is False
    assert any("challenger nao calibrado" in r for r in d["reasons"])


# ---- item 3 ---------------------------------------------------------------
def test_evaluate_purge_smaller_than_horizon():
    with pytest.raises(ValueError):
        evaluate_c1_vs_b1(synth(), horizons=(7, 15, 30), purge_days=15)


@pytest.fixture(scope="module")
def ev():
    return evaluate_c1_vs_b1(synth(), n_folds=2, n_boot=100, data_source="real")


def test_evaluate_output_not_vacuous(ev):
    n = len(ev["y"])
    assert n > 0
    assert n == len(ev["p_c1"]) == len(ev["p_b1"]) == len(ev["blocks"]) == len(ev["t"])
    assert all(0.0 <= p <= 1.0 for p in ev["p_c1"])
    assert ev["metrics"]["c1"]["brier"] >= 0
    assert "ci_low" in ev["ci_brier"] and "ci_low" in ev["ci_logloss"]
    assert isinstance(ev["calibrated"], bool)


def test_evaluate_purge_invariant(ev):
    assert ev["folds"]
    for f in ev["folds"]:
        assert f["train_max_first_seen"] <= f["test_min_t"] - timedelta(days=30)


def test_evaluate_late_first_seen_does_not_change_predictions(ev):
    recs = synth()
    extra = [mk(recs[40]["start_at"] + timedelta(days=3), fs=date(2030, 1, 1)),
             mk(recs[44]["start_at"] + timedelta(days=2), fs=date(2030, 1, 1))]
    ev2 = evaluate_c1_vs_b1(recs + extra, n_folds=2, n_boot=100, data_source="real")

    def idx(e):
        keys = zip(e["origin"], e["destination"], e["event_type"], e["t"], e["h"])
        return {k: (b, c) for k, b, c in zip(keys, e["p_b1"], e["p_c1"])}

    a, b = idx(ev), idx(ev2)
    common = set(a) & set(b)
    assert common
    for k in common:
        assert a[k] == b[k]


def test_evaluate_feeds_gate(ev):
    d = decide_champion(**ev["gate_inputs"])
    assert ev["n_campaigns_by_pair_type"][KEY] >= 25  # treino expansivo conta tudo
    assert not any("dados insuficientes" in r for r in d["reasons"])
    assert d["promoted"] is (not d["reasons"])  # decisao so deriva da avaliacao


def test_evaluate_few_campaigns_blocks_promotion():
    e = evaluate_c1_vs_b1(synth(n=30, step=7), n_folds=1, n_boot=50, data_source="real")
    assert e["n_campaigns_by_pair_type"][KEY] < 25
    d = decide_champion(**e["gate_inputs"])
    assert d["promoted"] is False
    assert any("< 25" in r for r in d["reasons"])


def test_evaluate_synthetic_flagged_records_not_counted():
    recs = synth()
    for r in recs:
        r["synthetic"] = True
    e = evaluate_c1_vs_b1(recs, n_folds=1, n_boot=50, data_source="real")
    assert e["n_campaigns_by_pair_type"][KEY] == 0
    assert decide_champion(**e["gate_inputs"])["promoted"] is False


def test_evaluate_default_data_source_is_synthetic():
    e = evaluate_c1_vs_b1(synth(), n_folds=1, n_boot=20)
    assert e["data_source"] == "synthetic"
    d = decide_champion(**e["gate_inputs"])
    assert d["promoted"] is False
    assert any("dados sintéticos" in r for r in d["reasons"])


# ---- item 4 ---------------------------------------------------------------
def test_bootstrap_requires_blocks():
    y = [0, 1] * 10
    p = [0.3, 0.7] * 10
    with pytest.raises(ValueError):
        block_bootstrap_ci(y, p, p, metric="brier", n_boot=10)
    assert "i // block_size" not in inspect.getsource(M)


# ---- item 5 ---------------------------------------------------------------
def test_report_banner_synthetic(tmp_path):
    d = decide_champion(**fav(), n_campaigns_by_pair_type={KEY: 30}, data_source="synthetic")
    p = tmp_path / "r.md"
    record_decision_report(d, path=str(p))
    txt = p.read_text()
    assert "SINTÉTICOS" in txt and "25" in txt
    assert "livelo,smiles,transfer_bonus" in txt


def test_report_no_banner_when_real_and_enough(tmp_path):
    d = decide_champion(**fav(), n_campaigns_by_pair_type={KEY: 30}, data_source="real")
    p = tmp_path / "r.md"
    record_decision_report(d, path=str(p))
    assert "SINTÉTICOS" not in p.read_text()


def test_report_banner_when_gate_fails_even_if_real(tmp_path):
    d = decide_champion(**fav(), n_campaigns_by_pair_type={KEY: 3}, data_source="real")
    p = tmp_path / "r.md"
    record_decision_report(d, path=str(p))
    assert "SINTÉTICOS" in p.read_text()


# ---- itens 6, 7 -------------------------------------------------------------
def test_probability_bounded():
    assert C1.LGB_PARAMS["min_child_samples"] >= 20
    out = M.predict_proba(HIST, "livelo", "smiles", "transfer_bonus",
                          as_of=date(2025, 7, 1), horizons=[7, 15, 30], method="c1")
    for h in (7, 15, 30):
        assert 0.01 <= out[h] <= 0.99


def test_monotonic_independent_of_request():
    kw = {"as_of": date(2025, 7, 1), "method": "c1"}
    args = (HIST, "livelo", "smiles", "transfer_bonus")
    full = M.predict_proba(*args, horizons=[7, 15, 30], **kw)
    only30 = M.predict_proba(*args, horizon=30, **kw)
    assert only30 == full[30]
    assert M.predict_proba(*args, horizons=[30], **kw)[30] == full[30]
    assert full[7] <= full[15] <= full[30]


# ---- item 8 -----------------------------------------------------------------
def test_sibling_features_no_double_count():
    t = date(2025, 6, 20)
    recs = [mk(date(2025, 6, 1)), mk(date(2025, 6, 15)),
            mk(date(2025, 6, 10), o="livelo", d="azul"),
            mk(date(2025, 6, 18), o="livelo", d="azul")]
    grade = build_daily_grade(recs, horizons=[7], t_values=[t])
    row = next(r for r in grade if (r["origin"], r["destination"]) == ("livelo", "smiles"))
    c = C1()
    vals, _ = c._feature_row("livelo", "smiles", "transfer_bonus", t, recs)
    feats = dict(zip(c.feature_names, vals, strict=True))
    assert row["sibling_offers_30d"] == 2
    assert feats["sibling_offers_30d"] == row["sibling_offers_30d"]
    assert feats["sibling_offers_7d"] == row["sibling_offers_7d"]


# ---- item 9 -----------------------------------------------------------------
def test_calibration_purged_and_same_booster():
    recs = synth(n=48, step=15)
    c = C1().fit(recs, as_of=date(2025, 1, 1))
    info = c.calibration_info
    assert info["purge_days"] == max(c.horizons)
    assert info["calib_min_t"] >= info["train_max_t"] + timedelta(days=max(c.horizons))
    for h in c.horizons:
        if c.calibrators.get(h) is not None:
            assert c.calibration_booster[h] is c.models[h]


# ---- item 10 ----------------------------------------------------------------
def test_migration_fixed_parent_single_head():
    src = (ROOT / "migrations/versions/0003_calendar_seed.py").read_text()
    assert "is_file" not in src
    assert 'down_revision = "0002"' in src
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    assert len(ScriptDirectory.from_config(cfg).get_heads()) == 1
