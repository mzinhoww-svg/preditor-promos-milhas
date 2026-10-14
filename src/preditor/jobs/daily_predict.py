"""Job diário: baseline B0/B1, predições e prediction_log (append-only)."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from preditor.alerts import register_alerts
from preditor.api.db import get_engine
from preditor.api.queries import fetch_prediction_accuracy
from preditor.baseline import _available, _effective_starts, predict_proba
from preditor.offer_filter import GAP_ONLY_SQL
from preditor.stop import StopRequested, check_stop

HORIZONS = (7, 15, 30)
MIN_CAMPAIGNS_B1 = 25


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _engine(engine=None):
    return engine if engine is not None else get_engine()


def fetch_offers(engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT origin, destination, event_type, start_at, end_at, bonus_pct, segmented, "
            "segment_label, first_seen_at, bonus_pct AS bp FROM offer "
            f"WHERE NOT {GAP_ONLY_SQL}"
        ))
        return [dict(r._mapping) for r in rows]


def pair_campaign_counts(offers: list[dict]) -> dict[tuple, int]:
    """Conta campanhas por chave a partir de ofertas já filtradas point-in-time."""
    counts: dict[tuple, int] = defaultdict(int)
    for o in offers:
        key = (o["origin"], o["destination"], o["event_type"], bool(o.get("segmented")), o.get("segment_label") or "")
        counts[key] += 1
    return counts


CODE_FILES = ("baseline.py", "jobs/daily_predict.py", "offer_filter.py", "records.py", "extract.py")


def code_hash() -> str:
    """Hash do código que produz a predição (baseline + job)."""
    root = Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    for name in CODE_FILES:
        h.update((root / name).read_bytes())
    return h.hexdigest()


def dataset_hash(offers: list[dict]) -> str:
    """Hash determinístico das ofertas conhecidas em as_of (entrada do modelo)."""
    rows = sorted(
        (
            str(o.get("origin")), str(o.get("destination")), str(o.get("event_type")),
            str(o.get("start_at")), str(o.get("bonus_pct")),
            bool(o.get("segmented")), str(o.get("segment_label") or ""), str(o.get("first_seen_at")),
        )
        for o in offers
    )
    return hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()


def record_model_run(engine, model_version: str, data_hash: str, metrics: dict, methods: dict) -> int:
    """Grava (ou reutiliza) o run do job diário (role='daily').

    Nunca altera is_champion: o campeão só muda pela decisão campeão × desafiante (T08b).
    Concorrência: índice único parcial + ON CONFLICT; quem perde a corrida lê o run vencedor.
    """
    chash = code_hash()
    params = {
        "mv": model_version, "t": datetime.now(UTC), "dv": data_hash, "ch": chash,
        "hp": json.dumps({"name": model_version, "version": "1.0.0", "methods": methods,
                          "min_campaigns_b1": MIN_CAMPAIGNS_B1}),
        "m": json.dumps(metrics),
    }
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, "
            "hyperparams, metrics, code_hash, is_champion, role) VALUES "
            "(:mv, :t, :dv, '1', CAST(:hp AS jsonb), CAST(:m AS jsonb), :ch, FALSE, 'daily') "
            "ON CONFLICT (model_version, dataset_version, code_hash) WHERE role = 'daily' DO NOTHING"
        ), params)
        row = conn.execute(text(
            "SELECT id FROM model_run WHERE role = 'daily' AND model_version = :mv "
            "AND dataset_version = :dv AND code_hash = :ch"
        ), params).one()
    return int(row[0])


def _quantile(sorted_vals: list[float], q: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _explanation(known_recs: list[dict], method: str, ao: date, probs: Any) -> dict[str, Any]:
    """Fatores do B0/B1 derivados só de ofertas conhecidas em as_of (sem vazamento)."""
    starts = [d for d, _w in _effective_starts(known_recs)]
    last = starts[-1] if starts else None
    gaps = sorted((b - a).days for a, b in itertools.pairwise(starts))
    median_gap = None
    if gaps:
        mid = len(gaps) // 2
        median_gap = float(gaps[mid]) if len(gaps) % 2 else (gaps[mid - 1] + gaps[mid]) / 2
    return {
        "as_of": str(ao),
        "method": method,
        "n_campaigns": len(starts),
        "last_campaign_start": str(last) if last else None,
        "days_since_last": (ao - last).days if last else None,
        "median_interval_days": median_gap,
        "min_campaigns_b1": MIN_CAMPAIGNS_B1,
        # B0 usa só a taxa base: recência/intervalo são contexto, não causa da probabilidade
        "probability_driven_by": "base_rate" if method == "b0" else "seasonal_hazard",
        "windows": {str(h): float(probs.get(h, 0.0)) if isinstance(probs, dict) else 0.0 for h in HORIZONS},
    }


def run_daily(as_of: Any = None, engine=None) -> dict[str, Any]:
    check_stop()
    eng = _engine(engine)
    ao = _as_date(as_of) if as_of is not None else date.today()
    made_at = datetime(ao.year, ao.month, ao.day, tzinfo=UTC)
    ao_dt = made_at
    # point-in-time: par, método (B0/B1) e bônus derivam só do que já era conhecido em as_of
    offers = [o for o in fetch_offers(eng) if _available(o, ao, ao_dt)]
    counts = pair_campaign_counts(offers)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for o in offers:
        key = (o["origin"], o["destination"], o["event_type"], bool(o.get("segmented")), o.get("segment_label") or "")
        groups[key].append(o)
    methods = {k: ("b1" if counts.get(k, 0) >= MIN_CAMPAIGNS_B1 else "b0") for k in groups}
    n_by_method = {m: sum(1 for v in methods.values() if v == m) for m in ("b0", "b1")}
    run_model = "B1" if n_by_method["b1"] else "B0"
    model_run_id = record_model_run(
        eng,
        model_version=run_model,
        data_hash=dataset_hash(offers),
        metrics={
            "n_offers": len(offers),
            "n_pairs": len(groups),
            "n_predictions": len(groups) * len(HORIZONS),
            "n_b0": n_by_method["b0"],
            "n_b1": n_by_method["b1"],
        },
        methods=n_by_method,
    )

    inserted_predictions = 0
    inserted_logs = 0
    for key, recs in groups.items():
        check_stop()  # STOP criado no meio da execução para antes do próximo grupo
        origin, destination, event_type, segmented, segment_label = key
        method = methods[key]
        # filtra registros conhecidos até as_of via baseline predict_proba
        probs = predict_proba(
            records=recs,
            origin=origin,
            destination=destination,
            event_type=event_type,
            method=method,
            as_of=ao,
            horizons=HORIZONS,
            segmented=segmented,
            segment_label=segment_label if segment_label else None,
        )
        # bonus percentis: apenas ofertas já conhecidas em as_of (point-in-time)
        known_recs = [o for o in recs if _available(o, ao, made_at)]
        bonus_vals = sorted(float(o["bonus_pct"]) for o in known_recs if o.get("bonus_pct") is not None)
        p25 = _quantile(bonus_vals, 0.25)
        p50 = _quantile(bonus_vals, 0.50)
        p75 = _quantile(bonus_vals, 0.75)

        explanation = _explanation(known_recs, method, ao, probs)
        for h in HORIZONS:
            p = float(probs.get(h, 0.0) if isinstance(probs, dict) else 0.0)
            with eng.begin() as conn:
                conn.execute(text(
                    "INSERT INTO prediction (made_at, model_run_id, origin, destination, event_type, "
                    "horizon_days, probability, bonus_p25, bonus_p50, bonus_p75, explanation) VALUES "
                    "(:made_at, :mr, :origin, :destination, :event_type, :h, :prob, :p25, :p50, :p75, "
                    "CAST(:ex AS jsonb)) "
                    "ON CONFLICT (made_at, model_run_id, origin, destination, event_type, horizon_days) DO NOTHING"
                ), {
                    "made_at": made_at,
                    "mr": model_run_id,
                    "origin": origin,
                    "destination": destination,
                    "event_type": event_type,
                    "h": int(h),
                    "prob": p,
                    "p25": p25,
                    "p50": p50,
                    "p75": p75,
                    "ex": json.dumps(explanation),
                })
                inserted_predictions += 1
            # prediction_log append-only, idempotente por chave lógica (+ constraint única no banco)
            model_version = "B1" if method == "b1" else "B0"
            with eng.begin() as conn:
                res = conn.execute(text(
                    "INSERT INTO prediction_log (logged_at, model_version, origin, destination, "
                    "event_type, horizon_days, probability) VALUES (:logged_at, :mv, :o, :d, :e, :h, :prob) "
                    "ON CONFLICT (model_version, origin, destination, event_type, horizon_days, "
                    "((logged_at AT TIME ZONE 'UTC')::date)) DO NOTHING"
                ), {
                    "logged_at": made_at,
                    "mv": model_version,
                    "o": origin,
                    "d": destination,
                    "e": event_type,
                    "h": int(h),
                    "prob": p,
                })
                inserted_logs += int(res.rowcount or 0)
    alerts = register_alerts(eng, made_at=made_at)
    return {
        "as_of": str(ao),
        "pairs": len(groups),
        "inserted_predictions": inserted_predictions,
        "inserted_logs": inserted_logs,
        "model_run_id": model_run_id,
        "alerts": alerts,
    }


def run_accuracy(as_of: Any = None, engine=None) -> dict[str, Any]:
    return fetch_prediction_accuracy(engine=engine) if False else fetch_prediction_accuracy()


# compatibility alias
def run_accuracy_job(*args, **kwargs):
    return run_accuracy(*args, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Job diário preditor")
    parser.add_argument("command", nargs="?", default="daily", choices=["daily", "accuracy", "all"])
    parser.add_argument("--as-of", dest="as_of", default=None)
    args = parser.parse_args(argv)
    try:
        if args.command in ("daily", "all"):
            res = run_daily(as_of=args.as_of)
            print(res)
        if args.command in ("accuracy", "all"):
            res = run_accuracy(as_of=args.as_of)
            print(res)
    except StopRequested as exc:
        print(f"STOP: {exc}")
        raise SystemExit(3) from exc


if __name__ == "__main__":
    main()
