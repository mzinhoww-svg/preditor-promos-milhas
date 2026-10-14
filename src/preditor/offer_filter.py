"""Filtro compartilhado: oferta cuja UNICA evidencia tem published_vs_capture_gap nao entra em
treino nem avaliacao ate revisao manual (condicao do PR #36)."""

# Verdadeiro quando a oferta tem evidencia e todas elas vem de mensagens com gap de publicacao.
GAP_ONLY_SQL = (
    "(EXISTS (SELECT 1 FROM offer_evidence g1 WHERE g1.offer_id = offer.id) "
    "AND NOT EXISTS (SELECT 1 FROM offer_evidence g2 JOIN raw_message gm ON gm.id = g2.raw_message_id "
    "WHERE g2.offer_id = offer.id AND gm.published_vs_capture_gap = FALSE))"
)
