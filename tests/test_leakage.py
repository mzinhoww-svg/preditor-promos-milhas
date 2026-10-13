from datetime import UTC, date, datetime

import pytest

from preditor.baseline import B0, predict_proba
from preditor.walkforward import walk_forward_splits


def mk(start, fs=None, **kw):
    r = {"origin": "livelo", "destination": "smiles", "event_type": "transfer_bonus", "start_at": start}
    if fs is not None: r["first_seen_at"] = fs
    r.update(kw); return r
BASE = [mk(date(2025, m, 10), date(2025, m, 10)) for m in (1, 3, 5, 7, 9, 11)]
T = date(2026, 1, 1)
FUT = [mk(date(2026, 6, 1), date(2026, 6, 1))] * 5
def p(recs, method="b1", **kw): return predict_proba(recs, "livelo", "smiles", "transfer_bonus", horizon=30, method=method, **kw)

def test_A_missing_first_seen(): assert p(BASE + [mk(date(2025, 12, 20))], "b0", as_of=T) == p(BASE, "b0", as_of=T)
def test_A2_invalid_first_seen(): assert p(BASE + [mk(date(2025, 12, 20), "lixo")], "b0", as_of=T) == p(BASE, "b0", as_of=T)
def test_B_no_as_of_raises():
    with pytest.raises(ValueError): p(BASE + FUT)
def test_C_typo_as_of_raises():
    with pytest.raises((ValueError, TypeError)): p(BASE + FUT, asof=T)
def test_C2_predict_typo_on_fitted_model():
    m = B0().fit(BASE + FUT, as_of=date(2026, 12, 31))
    with pytest.raises((ValueError, TypeError)): m.predict("livelo", "smiles", "transfer_bonus", asof=T, horizon=30)
def test_D_same_day_late_date_as_of():
    late = mk(date(2026, 1, 1), datetime(2026, 1, 1, 23, 0))
    assert p(BASE + [late], "b0", as_of=T) == p(BASE, "b0", as_of=T)
def test_D2_aware_vs_naive():
    p(BASE + [mk(date(2025, 12, 20), datetime(2025, 12, 20, 12, tzinfo=UTC))], "b0", as_of=T)
    p(BASE + [mk(date(2025, 12, 20), date(2025, 12, 20))], "b0", as_of=datetime(2026, 1, 1, tzinfo=UTC))
def test_V_validated_is_final_state():
    a = mk(date(2025, 12, 20), date(2025, 12, 20), validated=False, n_sources=1)
    b = mk(date(2025, 12, 20), date(2025, 12, 20), validated=True, n_sources=2)
    assert p(BASE + [a], "b0", as_of=T) == p(BASE + [b], "b0", as_of=T)
def test_F_late_first_seen():
    items = [mk(date(2025, m, 10), date(2025, m, 10)) for m in range(1, 7)]
    late = mk(date(2025, 2, 20), date(2025, 6, 25)); items.append(late)
    for s in walk_forward_splits(items, train_months=3, test_months=1, step_months=1, purge_days=30):
        assert not any(x is late for x in s.train) or s.test_start > date(2025, 6, 25)
def test_F2_first_seen_after_cutoff_before_test():
    a = mk(date(2025, 1, 5), date(2025, 2, 25))
    sp = walk_forward_splits([a, mk(date(2025, 3, 12), date(2025, 3, 12))], train_months=2, test_months=1, step_months=1, purge_days=30)
    assert not any(any(x is a for x in s.train) for s in sp)
def test_G_purge_from_window_start():
    sp = walk_forward_splits([mk(date(2025, 1, 31), date(2025, 1, 31)), mk(date(2025, 2, 28), date(2025, 2, 28))],
                            train_months=1, test_months=1, step_months=1, purge_days=30)
    assert all((date(2025, 2, 1) - s.train_end).days >= 15 for s in sp)
def test_X_expanding_true_keeps_old_months():
    items = [mk(date(2025, m, 10), date(2025, m, 10)) for m in range(1, 7)]
    sp = walk_forward_splits(items, train_months=2, test_months=1, step_months=1, purge_days=30, expanding=True)
    assert any(x["start_at"].month == 1 for x in sp[-1].train)
def test_H_horizon_vs_purge():
    with pytest.raises(ValueError):
        walk_forward_splits(BASE, train_months=2, test_months=1, purge_days=5, horizons=[7, 15, 30])

def test_R1_first_seen_as_date_same_day():
    assert p(BASE + [mk(T, T)], as_of=T) == p(BASE, as_of=T)
