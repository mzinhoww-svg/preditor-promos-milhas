"""Job diário: baseline B0/B1, predições e prediction_log (append-only)."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text

from preditor.api.db import get_engine
from preditor.api.queries import fetch_prediction_accuracy
from preditor.baseline import _available, predict_proba

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
            "segment_label, first_seen_at, bonus_pct AS bp FROM offer"
        ))
        return [dict(r._mapping) for r in rows]


def pair_campaign_counts(engine) -> dict[tuple, int]:
    offers = fetch_offers(engine)
    counts: dict[tuple, int] = defaultdict(int)
    for o in offers:
        key = (o["origin"], o["destination"], o["event_type"], bool(o.get("segmented")), o.get("segment_label") or "")
        counts[key] += 1
    return counts


def get_or_create_champion_model_run(engine, as_of: date) -> int:
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT id FROM model_run WHERE is_champion = TRUE ORDER BY trained_at DESC LIMIT 1"
        )).fetchone()
        if row is not None:
            return int(row[0])
        row = conn.execute(text(
            "INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, "
            "hyperparams, metrics, code_hash, is_champion) VALUES "
            "('B1', :trained_at, 'daily', '1', '{\"name\":\"B1\",\"version\":\"1.0.0\"}'::jsonb, "
            "'{}'::jsonb, 'daily-job', TRUE) RETURNING id"
        ), {"trained_at": datetime.now(UTC)}).fetchone()
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


def run_daily(as_of: Any = None, engine=None) -> dict[str, Any]:
    eng = _engine(engine)
    ao = _as_date(as_of) if as_of is not None else date.today()
    made_at = datetime(ao.year, ao.month, ao.day, tzinfo=UTC)
    offers = fetch_offers(eng)
    counts = pair_campaign_counts(eng)
    model_run_id = get_or_create_champion_model_run(eng, ao)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for o in offers:
        key = (o["origin"], o["destination"], o["event_type"], bool(o.get("segmented")), o.get("segment_label") or "")
        groups[key].append(o)

    inserted_predictions = 0
    inserted_logs = 0
    for key, recs in groups.items():
        origin, destination, event_type, segmented, segment_label = key
        n = counts.get(key, 0)
        method = "b1" if n >= MIN_CAMPAIGNS_B1 else "b0"
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

        for h in HORIZONS:
            p = float(probs.get(h, 0.0) if isinstance(probs, dict) else 0.0)
            with eng.begin() as conn:
                conn.execute(text(
                    "INSERT INTO prediction (made_at, model_run_id, origin, destination, event_type, "
                    "horizon_days, probability, bonus_p25, bonus_p50, bonus_p75) VALUES "
                    "(:made_at, :mr, :origin, :destination, :event_type, :h, :prob, :p25, :p50, :p75) "
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
    return {"as_of": str(ao), "pairs": len(groups), "inserted_predictions": inserted_predictions, "inserted_logs": inserted_logs}


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
    if args.command in ("daily", "all"):
        res = run_daily(as_of=args.as_of)
        print(res)
    if args.command in ("accuracy", "all"):
        res = run_accuracy(as_of=args.as_of)
        print(res)


if __name__ == "__main__":
    main()
