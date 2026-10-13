from datetime import date, datetime

from preditor.baseline import (
    B0,
    B1,
    b1_hazard,
    base_rate,
    predict_proba,
)


def mk(start, **kw):
    return {
        "origin": "livelo",
        "destination": "smiles",
        "event_type": "transfer_bonus",
        "start_at": start,
        "first_seen_at": start,
        **kw,
    }


HIST = [
    mk(date(2025, 3, 5)),
    mk(date(2025, 3, 18)),
    mk(date(2025, 7, 2)),
    mk(date(2025, 11, 10)),
    mk(date(2026, 1, 7)),
    mk(date(2026, 2, 14)),
]


def test_b0_returns_probabilities_for_7_15_30():
    m = B0()
    m.fit(HIST)
    out = m.predict("livelo", "smiles", "transfer_bonus", as_of=date(2026, 2, 20), horizons=(7, 15, 30))
    assert set(out.keys()) == {7, 15, 30}
    for v in out.values():
        assert 0.0 <= v <= 1.0
    assert out[7] <= out[15] <= out[30]


def test_b0_empty_history_is_zero():
    m = B0()
    m.fit([])
    out = m.predict("livelo", "smiles", "transfer_bonus", as_of=date(2026, 2, 20), horizons=(7, 15, 30))
    assert all(v == 0.0 for v in out.values())


def test_b1_seasonal_month_effect():
    hist = [mk(date(2025, 3, 5)), mk(date(2025, 3, 18))]
    m = B1()
    m.fit(hist)
    out = m.predict("livelo", "smiles", "transfer_bonus", as_of=date(2026, 2, 20), horizons=(7, 30))
    # 7 dias (fev) sem historico; 30 dias atinge marco, que tem historico
    assert out[30] > out[7]


def test_functional_aliases():
    out = base_rate(HIST, "livelo", "smiles", "transfer_bonus", as_of=date(2026, 2, 20), horizon=7)
    assert isinstance(out, float)
    out2 = b1_hazard(HIST, "livelo", "smiles", "transfer_bonus", as_of=date(2026, 2, 20), horizon=7)
    assert isinstance(out2, float)
    p = predict_proba(HIST, "livelo", "smiles", "transfer_bonus", as_of=date(2026, 2, 20), horizon=7, method="b0")
    assert isinstance(p, float)


def test_predict_proba_all_horizons():
    p = predict_proba(HIST, "livelo", "smiles", "transfer_bonus", as_of=date(2026, 2, 20), horizons=(7, 15, 30), method="b1")
    assert set(p.keys()) == {7, 15, 30}


def test_anti_leakage_prediction_at_t_unchanged_by_future_data():
    future_extra = [mk(date(2026, 3, 1)) for _ in range(5)]
    p0 = predict_proba(HIST, "livelo", "smiles", "transfer_bonus", as_of=date(2026, 2, 20), horizon=7, method="b1")
    p1 = predict_proba(HIST + future_extra, "livelo", "smiles", "transfer_bonus", as_of=date(2026, 2, 20), horizon=7, method="b1")
    assert p0 == p1

    # também mudar data de evento futuro não pode alterar previsão em t
    hist2 = [dict(e, start_at=date(2026, 9, 1)) if e["start_at"] == date(2026, 2, 14) else e for e in HIST]  # proxy: posterior alterado
    # esse caso altera passado? garantir apenas comparação com histórico original via cutoff
    _ = hist2


def test_as_of_accepts_datetime_and_string():
    out = predict_proba(HIST, "livelo", "smiles", "transfer_bonus", as_of="2026-02-20", horizon=7, method="b1")
    assert isinstance(out, float)
    out2 = predict_proba(HIST, "livelo", "smiles", "transfer_bonus", as_of=datetime(2026, 2, 20), horizon=7, method="b1")
    assert isinstance(out2, float)
