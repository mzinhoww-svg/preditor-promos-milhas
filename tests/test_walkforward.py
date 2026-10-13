from datetime import date, timedelta

from preditor.walkforward import (
    brier_score,
    log_loss,
    walk_forward_splits,
)


def mk(d, fs=None):
    r = {"origin": "livelo", "destination": "smiles", "event_type": "transfer_bonus", "start_at": d}
    r["first_seen_at"] = fs if fs is not None else d
    return r


HIST = [mk(date(2026, m, 15)) for m in range(1, 7)]


def test_walk_forward_splits_basic():
    splits = list(walk_forward_splits(HIST, purge_days=30, train_months=2, test_months=1, step_months=1))
    assert len(splits) >= 1
    for sp in splits:
        train, test = sp  # __iter__
        assert train and test
        tr_dates = [x["start_at"] for x in train]
        te_dates = [x["start_at"] for x in test]
        assert max(tr_dates) + timedelta(days=15) <= min(te_dates)


def test_walk_forward_no_overlap():
    splits = list(walk_forward_splits(HIST, purge_days=30, train_months=2, test_months=1, step_months=1))
    for sp in splits:
        train, test = sp
        tr_ids = {id(x) for x in train}
        te_ids = {id(x) for x in test}
        assert not (tr_ids & te_ids)


def test_purge_gap_respected_even_adjacent_months():
    # treino jan, teste fev: sem purge, adjacent; com purge remove todo fev
    items = [mk(date(2026, 1, 10), date(2025, 12, 20)), mk(date(2026, 2, 5)), mk(date(2026, 3, 20))]
    splits = list(walk_forward_splits(items, purge_days=15, horizons=[], train_months=1, test_months=1, step_months=1))
    found = False
    for sp in splits:
        train, test = sp
        if any(x["start_at"].month == 1 for x in train) and any(x["start_at"].month == 2 for x in test):
            found = True
    assert found


def test_metrics_brier_and_logloss():
    y = [0, 1, 1, 0]
    p = [0.1, 0.9, 0.8, 0.2]
    b = brier_score(y, p)
    l = log_loss(y, p)
    assert 0 <= b <= 1
    assert l > 0


def test_metric_perfect_prediction_low():
    y = [0, 1]
    p = [0.01, 0.99]
    assert brier_score(y, p) < 0.01
    assert log_loss(y, p) < 0.1


def test_split_metadata_available():
    splits = list(walk_forward_splits(HIST, purge_days=30, train_months=2, test_months=1, step_months=1))
    sp = splits[0]
    assert hasattr(sp, "train")
    assert hasattr(sp, "test")
    assert hasattr(sp, "train_end")
    assert hasattr(sp, "test_start")
    assert sp.test_start >= sp.train_end
