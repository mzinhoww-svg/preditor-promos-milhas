"""Consolidação de campanhas: dedup, validação cruzada e peso de treino.

Regras (ver docs/glossario.md): uma campanha vale com 1 fonte; validated exige
>= 2 fontes distintas com início a no máximo 3 dias entre si; divergência de datas
marca date_conflict e start_at usa a data mais antiga confiável.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

WINDOW_DAYS = 3
SINGLE_SOURCE_WEIGHT = 0.5
CampaignKey = tuple[str, str, str]  # (origem, destino, tipo)


@dataclass(frozen=True)
class Evidence:
    source: str
    start_at: date


@dataclass(frozen=True)
class Consolidated:
    start_at: date
    n_sources: int
    validated: bool
    date_conflict: bool
    weight: float


def same_campaign(key_a: CampaignKey, date_a: date, key_b: CampaignKey, date_b: date) -> bool:
    return key_a == key_b and abs((date_a - date_b).days) <= WINDOW_DAYS


def consolidate(evidences: list[Evidence]) -> Consolidated:
    if not evidences:
        raise ValueError("campanha sem evidência")
    # Mensagens repetidas da mesma fonte contam uma vez, com a data mais antiga.
    per_source: dict[str, date] = {}
    for e in evidences:
        if e.source not in per_source or e.start_at < per_source[e.source]:
            per_source[e.source] = e.start_at
    dates = sorted(per_source.values())

    best: list[date] = []
    for i, lo in enumerate(dates):
        cluster = [d for d in dates[i:] if (d - lo).days <= WINDOW_DAYS]
        if len(cluster) > len(best):
            best = cluster

    validated = len(best) >= 2
    start_at = best[0] if validated else dates[0]
    return Consolidated(
        start_at=start_at,
        n_sources=len(per_source),
        validated=validated,
        date_conflict=len(set(dates)) > 1,
        weight=1.0 if validated else SINGLE_SOURCE_WEIGHT,
    )
