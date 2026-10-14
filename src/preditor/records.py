"""Loader de registros de oferta para o T08 (treino/avaliacao) com a flag gap_only preenchida."""
from __future__ import annotations

from sqlalchemy import text

from preditor.offer_filter import GAP_ONLY_SQL


def load_offer_records(engine) -> list[dict]:
    """Ofertas com first_seen_at e `gap_only` (unica evidencia com published_vs_capture_gap).

    Passe o resultado a `model.exclude_gap_only`/`evaluate_c1_vs_b1`: registros gap_only ficam
    fora de treino e avaliacao ate a revisao manual.
    """
    sql = (
        "SELECT origin, destination, event_type, start_at, end_at, bonus_pct, segmented, segment_label, "
        f"first_seen_at, n_sources, validated, {GAP_ONLY_SQL} AS gap_only FROM offer ORDER BY start_at, id"
    )
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql))]
