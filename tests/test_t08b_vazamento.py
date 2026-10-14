"""T08b ciclo 3: testes de ataque que matam as mutacoes de vazamento M1, M2, M4, M7 (QA PR #38)."""
import random
from datetime import date, timedelta

from preditor import model as M
from preditor.model import C1, _available_offers, build_daily_grade, evaluate_c1_vs_b1


def mk(start, o="livelo", d="smiles", fs=None, tp="transfer_bonus"):
    return {"origin": o, "destination": d, "event_type": tp, "start_at": start,
            "first_seen_at": fs if fs is not None else start}


def world(seed=7):
    rnd = random.Random(seed)
    recs = []
    for o, d, step in (("livelo", "smiles", 14), ("esfera", "latam", 21), ("itau", "azul", 17)):
        t = date(2023, 1, 1)
        while t < date(2025, 6, 1):
            recs.append(mk(t, o, d, fs=t - timedelta(days=rnd.randint(0, 3))))
            t += timedelta(days=step + rnd.randint(-3, 3))
    return recs


def ev_run(recs, **kw):
    return evaluate_c1_vs_b1(recs, n_folds=2, n_boot=20, data_source="real", **kw)


def preds(e):
    keys = zip(e["origin"], e["destination"], e["event_type"], e["t"], e["h"], strict=True)
    return {k: (b, c) for k, b, c in zip(keys, e["p_b1"], e["p_c1"], strict=True)}


# ---- M1: _available_offers ignora t -----------------------------------------
def test_available_offers_drops_first_seen_after_t():
    t = date(2025, 3, 10)
    seen = mk(date(2025, 3, 1))
    backfill = mk(date(2025, 3, 2), fs=date(2025, 3, 20))  # start <= t, visto depois
    out = _available_offers([seen, backfill], t)
    assert out == [seen]


def test_feature_row_ignores_backfilled_records():
    t = date(2025, 3, 10)
    base = [mk(date(2025, 1, 5)), mk(date(2025, 2, 20)),
            mk(date(2025, 2, 25), d="azul")]
    backfill = [mk(date(2025, 3, 5), fs=date(2025, 4, 1)),
                mk(date(2025, 3, 6), d="azul", fs=date(2025, 4, 1))]
    c = C1()
    a, _ = c._feature_row("livelo", "smiles", "transfer_bonus", t, base)
    b, _ = c._feature_row("livelo", "smiles", "transfer_bonus", t, base + backfill)
    assert a == b
    feats = dict(zip(c.feature_names, a, strict=True))
    assert feats["n_known_offers"] == 2
    assert feats["days_since_last_offer"] == (t - date(2025, 2, 20)).days


# ---- M7: grade/features sem filtro fs <= t ------------------------------------
def test_grade_features_ignore_records_not_yet_seen():
    t = date(2025, 3, 10)
    base = [mk(date(2025, 1, 5)), mk(date(2025, 2, 20)), mk(date(2025, 2, 25), d="azul")]
    late = [mk(date(2025, 3, 5), fs=date(2025, 4, 1)),
            mk(date(2025, 3, 6), d="azul", fs=date(2025, 4, 1))]

    def row(recs):
        g = build_daily_grade(recs, horizons=[7], t_values=[t],
                              pairs={("livelo", "smiles")}, types={"transfer_bonus"})
        return next(r for r in g)

    r0, r1 = row(base), row(base + late)
    for k in ("n_known_offers", "days_since_last_offer", "sibling_offers_7d",
              "sibling_offers_30d"):
        assert r0[k] == r1[k], k
    assert r0["n_known_offers"] == 2


def test_features_for_example_ignores_future_first_seen_sibling():
    t = date(2025, 3, 10)
    sib_seen = mk(date(2025, 3, 1), d="azul")
    sib_late = mk(date(2025, 3, 2), d="azul", fs=date(2025, 3, 25))
    f = M._features_for_example("livelo", "smiles", "transfer_bonus", t,
                                [sib_seen, sib_late], [], None, (7, 30))
    assert f["sibling_offers_30d"] == 1


# ---- M4: fit com as_of futuro ---------------------------------------------------
def test_each_fold_fit_only_sees_cutoff():
    e = ev_run(world())
    assert len(e["folds"]) == 2
    for f in e["folds"]:
        assert f["fit_as_of"] == f["cutoff"]
        assert f["fit_max_first_seen"] <= f["cutoff"]
        assert f["fit_n_records"] == f["n_train"] > 0
        assert f["cutoff"] <= f["test_min_t"] - timedelta(days=30)


# ---- M2: treino sem cutoff/purge --------------------------------------------------
def test_training_filters_first_seen_even_if_splitter_leaks(monkeypatch):
    import preditor.walkforward as wf

    clean = ev_run(world())
    real = wf.walk_forward_splits

    def leaky(items, **kw):
        splits = real(items, **kw)
        for sp in splits:
            tr = sp.train[0]
            leak = dict(tr)
            leak["first_seen_at"] = sp.test_start + timedelta(days=5)  # depois do corte
            sp.train.append(leak)
        return splits

    monkeypatch.setattr(wf, "walk_forward_splits", leaky)
    dirty = ev_run(world())
    for fc, fd in zip(clean["folds"], dirty["folds"], strict=True):
        assert fd["n_train"] == fc["n_train"]
        assert fd["train_max_first_seen"] <= fd["cutoff"]
    assert preds(dirty) == preds(clean)


# ---- invariancia por dobra com registros tardios dentro da janela de teste ---------
def test_late_records_inside_test_window_do_not_change_predictions():
    recs = world()
    base = ev_run(recs)
    rnd = random.Random(1)
    late = [mk(r["start_at"] + timedelta(days=2), r["origin"], r["destination"],
               fs=date(2026, 6, 1) + timedelta(days=i))
            for i, r in enumerate(rnd.sample(recs, 40))]
    alt = ev_run(recs + late)
    a, b = preds(base), preds(alt)
    common = set(a) & set(b)
    assert len(common) > 500
    assert [k for k in common if a[k] != b[k]] == []


def test_evaluation_is_deterministic():
    r = world()
    assert preds(ev_run(r)) == preds(ev_run(list(reversed(r))))
