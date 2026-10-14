"""Alertas: registra quando a probabilidade de um item cruza o limiar (apenas tabela/endpoint)."""
from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import text

DEFAULT_THRESHOLD = 0.5


def alert_threshold() -> float:
    raw = (os.environ.get("PREDITOR_ALERT_THRESHOLD") or "").strip()
    if not raw:
        return DEFAULT_THRESHOLD
    try:
        val = float(raw)
    except ValueError:
        return DEFAULT_THRESHOLD
    return val if 0.0 < val < 1.0 else DEFAULT_THRESHOLD


_SQL = """
INSERT INTO alert (made_at, model_run_id, origin, destination, event_type, horizon_days,
                   probability, previous_probability, threshold)
SELECT cur.made_at, cur.model_run_id, cur.origin, cur.destination, cur.event_type, cur.horizon_days,
       cur.probability, prev.probability, :thr
FROM prediction cur
LEFT JOIN LATERAL (
    SELECT p.probability FROM prediction p
    WHERE p.origin = cur.origin AND p.destination = cur.destination
      AND p.event_type = cur.event_type AND p.horizon_days = cur.horizon_days
      AND p.made_at < cur.made_at
    ORDER BY p.made_at DESC, p.model_run_id DESC LIMIT 1
) prev ON TRUE
WHERE cur.made_at = :made_at
  AND cur.probability >= :thr
  AND (prev.probability IS NULL OR prev.probability < :thr)
ON CONFLICT (made_at, origin, destination, event_type, horizon_days, threshold) DO NOTHING
"""


def register_alerts(engine, made_at: datetime, threshold: float | None = None) -> int:
    """Cruzamento ascendente: prob >= limiar agora e < limiar na rodada anterior (ou sem anterior)."""
    thr = alert_threshold() if threshold is None else float(threshold)
    with engine.begin() as conn:
        res = conn.execute(text(_SQL), {"made_at": made_at, "thr": thr})
        return int(res.rowcount or 0)
