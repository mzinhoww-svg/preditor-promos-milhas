"""Consultas de leitura no Postgres."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from preditor.offer_filter import GAP_ONLY_SQL

from .db import get_engine


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rows(result) -> list[dict]:
    return [dict(r._mapping) for r in result]


def fetch_predictions(type_filter: str | None = None, limit: int = 50) -> dict[str, Any]:
    engine = get_engine()
    with engine.connect() as conn:
        params = {}
        where = ""
        if type_filter:
            where = "WHERE event_type = :t"
            params["t"] = type_filter
        rows = _rows(conn.execute(text(
            f"SELECT made_at, model_run_id, origin, destination, event_type, horizon_days, probability, bonus_p25, bonus_p50, bonus_p75 "
            f"FROM (SELECT DISTINCT ON (origin, destination, event_type, horizon_days) * FROM prediction {where} "
            f"ORDER BY origin, destination, event_type, horizon_days, made_at DESC, model_run_id DESC) p "
            f"ORDER BY made_at DESC"
        ), params))
    generated_at = _now()
    # agrupa por made_at mais recente por item
    if rows:
        latest_made = max(r["made_at"] for r in rows)
        generated_at = latest_made.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z") if hasattr(latest_made, "astimezone") else _now()
    # group
    groups: dict[tuple, dict] = {}
    for r in rows:
        key = (r["origin"], r["destination"], r["event_type"])
        g = groups.setdefault(key, {"prob": {}, "made_at": r["made_at"], "mr": r["model_run_id"], "bonus": (r.get("bonus_p25"), r.get("bonus_p50"), r.get("bonus_p75"))})
        h = str(r["horizon_days"])
        g["prob"][h] = float(r["probability"])
    items = []
    for idx, ((origin, destination, etype), g) in enumerate(groups.items(), start=1):
        wins = {}
        for h in ("7", "15", "30"):
            p = g["prob"].get(h)
            if p is None:
                continue
            wins[h] = {"probability": p, "ci_low": p, "ci_high": p}
        # all three windows if any
        for h in ("7", "15", "30"):
            if h not in wins:
                wins[h] = {"probability": 0.0, "ci_low": 0.0, "ci_high": 0.0}
        b25, b50, b75 = g["bonus"]
        items.append({
            "rank": idx,
            "pair": {"origin": origin, "destination": destination},
            "type": etype,
            "segmented": False,
            "segment_label": None,
            "windows": wins,
            "bonus_pct": {"p25": b25, "p50": b50, "p75": b75},
            "last_offer": None,
            "reasons": [],
        })
    items.sort(key=lambda x: (-(x["windows"]["30"]["probability"]), -(x["windows"]["7"]["probability"])))
    for i, it in enumerate(items, start=1):
        it["rank"] = i
    if limit:
        items = items[:limit]
    model = fetch_model_info()
    return {"generated_at": generated_at, "model": model, "items": items}


def fetch_model_info() -> dict[str, Any]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = _rows(conn.execute(text(
            "SELECT id, model_version, trained_at, hyperparams, metrics, is_champion FROM model_run ORDER BY is_champion DESC, trained_at DESC"
        )))
    champion = None
    challenger = None
    for r in rows:
        if champion is None and r.get("is_champion"):
            champion = r
        elif challenger is None and not r.get("is_champion"):
            challenger = r
    if champion is None and rows:
        champion = rows[0]
    def _name_version(run):
        if not run:
            return {"name": None, "version": None, "trained_at": None, "run_id": None}
        hv = run.get("hyperparams") or {}
        mv = str(run.get("model_version") or "")
        name = hv.get("name") or (mv.split()[0] if mv else None)
        version = hv.get("version") or (mv.split()[1] if len(mv.split()) > 1 else None)
        trained = run.get("trained_at")
        trained_iso = trained.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z") if hasattr(trained, "astimezone") else (str(trained) if trained else None)
        return {"name": name, "version": version, "trained_at": trained_iso, "run_id": f"mr_{run.get('id')}"}
    ch = _name_version(champion)
    c = _name_version(challenger)
    return {
        "run_id": ch["run_id"],
        "name": ch["name"] or "B1",
        "version": ch["version"] or "1.0.0",
        "role": "champion",
        "champion": ch,
        "challenger": c,
    }


def fetch_source_health() -> dict[str, Any]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = _rows(conn.execute(text(
            "SELECT source, checked_at, items_new, extraction_rate, alert FROM source_health ORDER BY checked_at DESC"
        )))
    sources = []
    seen = set()
    for r in rows:
        if r["source"] in seen:
            continue
        seen.add(r["source"])
        sources.append({
            "source": r["source"],
            "kind": "rss",
            "status": "degraded" if r.get("alert") else "ok",
            "last_success_at": r["checked_at"].astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z") if hasattr(r["checked_at"], "astimezone") else None,
            "last_item_at": None,
            "items_new_24h": r.get("items_new"),
            "items_new_7d": r.get("items_new"),
            "extraction_rate_7d": float(r["extraction_rate"]) if r.get("extraction_rate") is not None else None,
            "error_rate_24h": 0.0 if not r.get("alert") else 0.1,
            "robots_hash": None,
            "robots_changed": False,
            "message": None,
        })
    return {"generated_at": _now(), "sources": sources}


def _resolve_prediction_outcomes():
    engine = get_engine()
    with engine.connect() as conn:
        logs = _rows(conn.execute(text(
            "SELECT id, logged_at, model_version, origin, destination, event_type, horizon_days, probability FROM prediction_log ORDER BY logged_at"
        )))
        offers = _rows(conn.execute(text(f"SELECT origin, destination, event_type, start_at FROM offer WHERE NOT {GAP_ONLY_SQL}")))
    return logs, offers


def fetch_prediction_accuracy(date_from=None, date_to=None, horizon=None) -> dict[str, Any]:
    logs, offers = _resolve_prediction_outcomes()
    from datetime import date as _date

    def _d(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, _date):
            return v
        return _date.fromisoformat(str(v)[:10])

    if date_from:
        df = _date.fromisoformat(str(date_from)[:10])
        logs = [x for x in logs if _d(x["logged_at"]) >= df]
    if date_to:
        dt = _date.fromisoformat(str(date_to)[:10])
        logs = [x for x in logs if _d(x["logged_at"]) <= dt]
    if horizon is not None:
        logs = [x for x in logs if int(x["horizon_days"]) == int(horizon)]


    def hit(log):
        h = int(log["horizon_days"])
        logged = log["logged_at"]
        ldate = logged.date() if hasattr(logged, "date") else _date.fromisoformat(str(logged)[:10])
        key = (log["origin"], log["destination"], log["event_type"])
        # oferta ocorreu dentro de h dias?
        for o in offers:
            if (o["origin"], o["destination"], o["event_type"]) != key:
                continue
            s = o["start_at"]
            sd = s.date() if hasattr(s, "date") else _date.fromisoformat(str(s)[:10])
            delta = (sd - ldate).days
            if 0 < delta <= h:
                return 1
        return 0

    by: dict[str, dict] = defaultdict(lambda: {"n": 0, "hits": 0, "brier_sum": 0.0, "ll_sum": 0.0})
    weekly: list[dict] = []
    from datetime import date as _today_date
    today = _today_date.today()
    resolved_logs = []
    for lg in logs:
        h = int(lg["horizon_days"])
        ld = _d(lg["logged_at"])
        if ld is None or (ld + timedelta(days=h)) > today:
            continue
        resolved_logs.append(lg)
    logs = resolved_logs
    for lg in logs:
        h = str(lg["horizon_days"])
        p = float(lg["probability"])
        y = hit(lg)
        import math
        brier = (p - y) ** 2
        ll = -(y * math.log(max(p, 1e-9)) + (1 - y) * math.log(max(1 - p, 1e-9)))
        by[h]["n"] += 1
        by[h]["hits"] += y
        by[h]["brier_sum"] += brier
        by[h]["ll_sum"] += ll
    by_horizon = {}
    for h, d in by.items():
        n = d["n"] or 1
        by_horizon[h] = {
            "n": d["n"],
            "hit_rate": d["hits"] / n,
            "brier": d["brier_sum"] / n,
            "log_loss": d["ll_sum"] / n,
        }
    if not by_horizon:
        for h in ("7", "15", "30"):
            by_horizon[h] = {"n": 0, "hit_rate": 0.0, "brier": 0.0, "log_loss": 0.0}

    return {
        "generated_at": _now(),
        "period": {"from": date_from or (min((log["logged_at"] for log in logs), default=None) and str(min(l["logged_at"] for l in logs))[:10]) or None, "to": date_to or (_now()[:10])},
        "by_horizon": by_horizon,
        "weekly": weekly,
        "alerts": [],
    }


def fetch_model_metrics() -> dict[str, Any]:
    info = fetch_model_info()
    champion = info.get("champion", {})
    cinfo = info.get("challenger", {}) or {}
    now = _now()
    def empty_model(run, name_default):
        run = run or {}
        hv = run.get("hyperparams") or {} if isinstance(run, dict) else {}
        metrics = run.get("metrics") if isinstance(run, dict) else {}
        metrics = metrics or {}
        trained = run.get("trained_at") if isinstance(run, dict) else None
        trained_iso = trained.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z") if hasattr(trained, "astimezone") else (str(trained) if trained else None)
        return {
            "name": (hv.get("name") if isinstance(hv, dict) else None) or run.get("model_version") or name_default,
            "version": (hv.get("version") if isinstance(hv, dict) else None) or "1.0.0",
            "trained_at": trained_iso or now,
            "horizons": [7, 15, 30],
            "validation": metrics.get("validation", {"method": "walk-forward", "folds": 0, "period": {"from": None, "to": None}, "by_horizon": {}}),
            "production": metrics.get("production", None),
        }
    return {
        "generated_at": now,
        "champion": empty_model(champion, "B1"),
        "challenger": (empty_model(cinfo, "C1") if (cinfo and cinfo.get("run_id")) else None),
        "comparison": {
            "horizon": 30,
            "delta_brier": 0.0,
            "delta_log_loss": 0.0,
            "ci_delta_brier": [0.0, 0.0],
            "decision": "keep_champion",
            "note": "sem dados suficientes",
        },
        "reliability": {"horizon": 30, "bins": []},
    }
