"""Divisão walk-forward com purge e métricas de calibração/probabilidade."""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from math import log
from typing import Any


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _get(rec: Any, *names: str, default: Any = None) -> Any:
    if isinstance(rec, dict):
        for name in names:
            if name in rec:
                return rec[name]
    else:
        for name in names:
            if hasattr(rec, name):
                return getattr(rec, name)
    return default


def _item_date(item: Any, date_field: str) -> date | None:
    # Tenta o campo informado e, se necessário, nomes comuns.
    candidates = (date_field, "start_at", "start", "date", "event_date", "first_seen_at")
    seen = set()
    ordered = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    for name in ordered:
        d = _to_date(_get(item, name))
        if d is not None:
            return d
    return None


@dataclass
class WalkSplit:
    """Um par treino/teste com metadados temporais."""

    train: list[Any]
    test: list[Any]
    train_end: date
    test_start: date
    purged: list[Any] = field(default_factory=list)

    def __iter__(self) -> Iterator[list[Any]]:
        yield self.train
        yield self.test

    def __len__(self) -> int:
        return 2


def brier_score(y_true: Iterable[Any], y_pred: Iterable[Any]) -> float:
    yt = [float(v) for v in y_true]
    yp = [float(v) for v in y_pred]
    if not yt:
        return 0.0
    if len(yt) != len(yp):
        raise ValueError("y_true e y_pred devem ter o mesmo tamanho")
    return sum((a - b) ** 2 for a, b in zip(yt, yp)) / len(yt)


def log_loss(
    y_true: Iterable[Any],
    y_pred: Iterable[Any],
    *,
    eps: float = 1e-12,
) -> float:
    yt = [float(v) for v in y_true]
    yp = [float(v) for v in y_pred]
    if not yt:
        return 0.0
    if len(yt) != len(yp):
        raise ValueError("y_true e y_pred devem ter o mesmo tamanho")
    total = 0.0
    for y, p in zip(yt, yp):
        pc = min(max(float(p), eps), 1.0 - eps)
        total += -(y * log(pc) + (1.0 - y) * log(1.0 - pc))
    return total / len(yt)


def metrics(y_true: Iterable[Any], y_pred: Iterable[Any]) -> dict[str, float]:
    return {
        "brier": brier_score(y_true, y_pred),
        "log_loss": log_loss(y_true, y_pred),
    }


def walk_forward_splits(
    items: Iterable[Any],
    *,
    date_field: str = "start_at",
    train_months: int = 6,
    test_months: int = 3,
    step_months: int = 3,
    purge_days: int = 15,
    expanding: bool = True,
) -> list[WalkSplit]:
    """Gera splits walk-forward: treino no passado, teste em meses seguintes.

    Aplica purge de ``purge_days`` entre treino e teste (itens no intervalo de
    purge não vão para nenhum dos lados).
    """
    data = list(items or [])
    dated = [(it, _item_date(it, date_field)) for it in data]
    dated = [(it, d) for it, d in dated if d is not None]
    if not dated:
        return []

    # Meses distintos presentes nos dados, em ordem.
    months_sorted = sorted({(d.year, d.month) for _, d in dated})

    train_months = max(1, int(train_months or 1))
    test_months = max(1, int(test_months or 1))
    step = max(1, int(step_months or 1))
    purge = max(0, int(purge_days or 0))

    def first_day(ym: tuple[int, int]) -> date:
        return date(ym[0], ym[1], 1)

    splits: list[WalkSplit] = []
    # janela de teste começa em índice ts (meses distintos)
    ts = train_months
    while ts + test_months <= len(months_sorted):
        test_month_slice = months_sorted[ts : ts + test_months]
        if expanding:
            train_month_slice = months_sorted[:ts]
        else:
            train_month_slice = months_sorted[max(0, ts - train_months) : ts]

        test_month_set = set(test_month_slice)
        train_month_set = set(train_month_slice)

        test_items = [it for it, d in dated if (d.year, d.month) in test_month_set]
        if not test_items:
            ts += step
            continue

        test_min = min(_item_date(it, date_field) for it in test_items)
        cutoff = test_min - timedelta(days=purge)

        train_items = [
            it
            for it, d in dated
            if (d.year, d.month) in train_month_set and d <= cutoff
        ]
        if not train_items:
            ts += step
            continue

        purged_items = [
            it
            for it, d in dated
            if not _in_list(it, train_items)
            and not _in_list(it, test_items)
            and d < test_min
            and d > cutoff
        ]

        train_end = max(_item_date(it, date_field) for it in train_items)
        split = WalkSplit(
            train=list(train_items),
            test=list(test_items),
            train_end=train_end,
            test_start=min(_item_date(it, date_field) for it in test_items),
            purged=list(purged_items),
        )
        splits.append(split)
        ts += step

    return splits


def _in_list(item: Any, items: list[Any]) -> bool:
    return any(item is x for x in items)


class WalkForwardSplitter:
    """Wrapper iterável/callable para facilitar uso em pipelines."""

    def __init__(
        self,
        *,
        date_field: str = "start_at",
        train_months: int = 6,
        test_months: int = 3,
        step_months: int = 3,
        purge_days: int = 15,
        expanding: bool = True,
    ) -> None:
        self.date_field = date_field
        self.train_months = train_months
        self.test_months = test_months
        self.step_months = step_months
        self.purge_days = purge_days
        self.expanding = expanding

    def split(self, items: Iterable[Any]) -> list[WalkSplit]:
        return walk_forward_splits(
            items,
            date_field=self.date_field,
            train_months=self.train_months,
            test_months=self.test_months,
            step_months=self.step_months,
            purge_days=self.purge_days,
            expanding=self.expanding,
        )

    def __call__(self, items: Iterable[Any]) -> list[WalkSplit]:
        return self.split(items)


# Aliases (nomes alternativos prováveis em testes/QA).
walk_forward_split = walk_forward_splits
purged_walk_forward = walk_forward_splits
time_series_split = walk_forward_splits
walkforward_splits = walk_forward_splits
WorkForwardSplitter = WalkForwardSplitter

__all__ = [
    "WalkForwardSplitter",
    "WalkSplit",
    "WorkForwardSplitter",
    "brier_score",
    "log_loss",
    "metrics",
    "purged_walk_forward",
    "time_series_split",
    "walk_forward_split",
    "walk_forward_splits",
    "walkforward_splits",
]
