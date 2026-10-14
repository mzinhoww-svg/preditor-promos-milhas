"""Loader de registros de oferta para o T08 (treino/avaliacao) com a flag gap_only preenchida."""
from __future__ import annotations

from sqlalchemy import text

from preditor.offer_filter import GAP_ONLY_SQL

# first_seen_at point-in-time: so evidencias SEM gap de publicacao (ate a revisao manual); a oferta
# so-gap mantem o valor da tabela, mas sai de treino/avaliacao por gap_only.
_FIRST_SEEN_NO_GAP = (
    "COALESCE((SELECT min(rm.observed_at) FROM offer_evidence oe JOIN raw_message rm ON rm.id = oe.raw_message_id "
    "WHERE oe.offer_id = offer.id AND rm.published_vs_capture_gap = FALSE AND rm.observed_at IS NOT NULL), "
    "offer.first_seen_at)"
)


def load_offer_records(engine) -> list[dict]:
    """Ofertas com first_seen_at (so evidencias sem gap) e `gap_only`.

    Nao expoe `validated`, `n_sources` nem `weight`: sao estado final (consolidado depois) e nao
    podem virar feature ou peso sem versao point-in-time (APR-008; guardado por teste).
    Passe o resultado a `model.exclude_gap_only`/`evaluate_c1_vs_b1`.
    """
    sql = (
        "SELECT origin, destination, event_type, start_at, end_at, bonus_pct, segmented, segment_label, "
        f"{_FIRST_SEEN_NO_GAP} AS first_seen_at, {GAP_ONLY_SQL} AS gap_only FROM offer ORDER BY start_at, id"
    )
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql))]
