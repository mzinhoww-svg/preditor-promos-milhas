from datetime import date, timedelta

from preditor.model import (
    block_bootstrap_ci,
    build_daily_grade,
    decide_champion,
    is_calibrated,
    record_decision_report,
)


def mk(start, fs=None):
    return {"origin": "livelo", "destination": "smiles", "event_type": "transfer_bonus",
            "start_at": start, "first_seen_at": (fs if fs is not None else start)}


def test_grade_label_embargo():
    recs = [mk(date(2025, 3, 5)), mk(date(2025, 3, 12))]
    grade = build_daily_grade(recs, horizons=[7])
    assert any(r["y"] == 1 for r in grade)
    # embargo: cutoff before first offer keeps early examples but excludes label window beyond cutoff
    grade2 = build_daily_grade(recs, horizons=[7], embargo_cutoff=date(2025, 3, 1))
    assert all((r["t"] + timedelta(days=r["h"])) <= date(2025, 3, 1) for r in grade2)


def test_point_in_time_model():
    hist = [mk(date(2025, m, 10)) for m in range(1, 7)]
    future = [mk(date(2025, 12, 1)) for _ in range(3)]
    p0 = __import__("preditor.model", fromlist=["predict_proba"]).predict_proba(
        hist, "livelo", "smiles", "transfer_bonus", as_of=date(2025, 7, 1), horizon=7, method="c1")
    p1 = __import__("preditor.model", fromlist=["predict_proba"]).predict_proba(
        hist + future, "livelo", "smiles", "transfer_bonus", as_of=date(2025, 7, 1), horizon=7, method="c1")
    assert p0 == p1


def test_bootstrap_ci_excludes_zero_when_clear():
    y = [0, 0, 1, 1] * 20
    pred_b1 = [0.4 if yy == 1 else 0.6 for yy in y]
    pred_c1 = [0.8 if yy == 1 else 0.2 for yy in y]
    blocks = [i // 5 for i in range(len(y))]
    ci = block_bootstrap_ci(y, pred_b1, pred_c1, blocks=blocks, metric="brier", n_boot=200, seed=1)
    assert ci["excludes_zero"] is True


def test_champion_keeps_b1_when_not_better():
    d = decide_champion(
        champion_metrics={"brier": 0.1, "log_loss": 0.3},
        challenger_metrics={"brier": 0.12, "log_loss": 0.35},
        bootstrap_ci_brier={"ci_low": -0.01, "ci_high": 0.02},
        bootstrap_ci_logloss={"ci_low": -0.01, "ci_high": 0.02},
        challenger_calibrated=True,
        n_campaigns_by_pair_type={("livelo", "smiles", "transfer_bonus"): 30},
        data_source="real",
    )
    assert d["decision"] == "keep_champion"
    assert d["promoted"] is False


def test_is_calibrated_basic():
    y = [0, 0, 1, 1]
    p = [0.1, 0.2, 0.8, 0.9]
    assert is_calibrated(y, p, tol=0.5, min_n=1) is True


def test_record_decision_report(tmp_path):
    p = tmp_path / "report.md"
    decision = {"decision": "keep_champion", "note": "motivo: C1 nao vence"}
    out = record_decision_report(decision, path=str(p))
    assert p.exists()
    assert "keep_champion" in p.read_text()
    assert out == str(p)
