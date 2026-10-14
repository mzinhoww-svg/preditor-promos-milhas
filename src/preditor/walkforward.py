"""Divisao walk-forward com purge e metricas calibradas."""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from math import log
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
HORIZONS_DEFAULT = (7, 15, 30)


def _normalize_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=TZ)
        return value.astimezone(TZ)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=TZ)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.strip())
        except ValueError:
            try:
                dt = datetime.combine(date.fromisoformat(value.strip()[:10]), time.min)
            except ValueError as exc:
                raise ValueError(f"data invalida: {value!r}") from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    raise ValueError(f"data invalida: {value!r}")

def _to_date(value: Any) -> date:
    return _normalize_datetime(value).date()


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


def _item_date(item: Any, date_field: str) -> date:
    v = _get(item, date_field)
    if v is None:
        raise ValueError(f"campo de data ausente: {date_field}")
    return _to_date(v)


def _first_seen_dt(item: Any) -> datetime | None:
    v = _get(item, "first_seen_at", "first_seen", default=None)
    if v is None:
        return None
    try:
        return _normalize_datetime(v)
    except (ValueError, TypeError):
        return None


def _validate_int(value: Any, name: str, min_value: int = 1) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve ser inteiro") from exc
    if iv < min_value:
        raise ValueError(f"{name} deve ser >= {min_value}")
    return iv


def _validate_purge(value: Any) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("purge_days deve ser inteiro") from exc
    if iv < 0:
        raise ValueError("purge_days deve ser >= 0")
    return iv


def _add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


@dataclass
class WalkSplit:
    train: list[Any]
    test: list[Any]
    train_end: date
    test_start: date
    purged: list[Any] = field(default_factory=list)
    dropped: list[Any] = field(default_factory=list)

    def __iter__(self) -> Iterator[list[Any]]:
        yield self.train
        yield self.test

    def __len__(self) -> int:
        return 2


def brier_score(y_true: Iterable[Any], y_pred: Iterable[Any]) -> float:
    yt = [float(v) for v in y_true]
    yp = [float(v) for v in y_pred]
    if not yt:
        raise ValueError("lista vazia nao permitida")
    if len(yt) != len(yp):
        raise ValueError("y_true e y_pred devem ter o mesmo tamanho")
    for y, p in zip(yt, yp):
        if y not in (0.0, 1.0):
            raise ValueError("y_true deve conter apenas 0 ou 1")
        if __import__('math').isnan(p) or __import__('math').isinf(p):
            raise ValueError("y_pred nao pode ser NaN ou infinito")
        if p < 0.0 or p > 1.0:
            raise ValueError("y_pred deve estar em [0, 1]")
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
        raise ValueError("lista vazia nao permitida")
    if len(yt) != len(yp):
        raise ValueError("y_true e y_pred devem ter o mesmo tamanho")
    for y, p in zip(yt, yp):
        if y not in (0.0, 1.0):
            raise ValueError("y_true deve conter apenas 0 ou 1")
        if __import__('math').isnan(p) or __import__('math').isinf(p):
            raise ValueError("y_pred nao pode ser NaN ou infinito")
        if p < 0.0 or p > 1.0:
            raise ValueError("y_pred deve estar em [0, 1]")
    total = 0.0
    for y, p in zip(yt, yp):
        pc = min(max(p, eps), 1.0 - eps)
        total += -(y * log(pc) + (1.0 - y) * log(1.0 - pc))
    return total / len(yt)


def metrics(y_true: Iterable[Any], y_pred: Iterable[Any]) -> dict[str, float]:
    return {"brier": brier_score(y_true, y_pred), "log_loss": log_loss(y_true, y_pred)}


def walk_forward_splits(
    items: Iterable[Any],
    *,
    date_field: str = "start_at",
    train_months: int = 6,
    test_months: int = 3,
    step_months: int = 3,
    purge_days: int = 30,
    expanding: bool = True,
    horizons: Iterable[int] | None = None,
) -> list[WalkSplit]:
    train_months = _validate_int(train_months, "train_months", 1)
    test_months = _validate_int(test_months, "test_months", 1)
    step_months = _validate_int(step_months, "step_months", 1)
    purge_days = _validate_purge(purge_days)
    horizons_list = list(horizons) if horizons is not None else None
    if horizons_list is None:
        effective_horizons = list(HORIZONS_DEFAULT)
    else:
        effective_horizons = horizons_list
    for h in effective_horizons:
        _validate_int(h, "horizon", 1)
    if effective_horizons and purge_days < max(effective_horizons):
        raise ValueError("purge_days deve ser >= max(horizons)")

    data = list(items) if items is not None else []
    # Validar no-op para horizons se fornecido: apenas confere >=1
    if horizons is not None:
        for h in horizons:
            _validate_int(h, "horizon", 1)

    dated: list[tuple[Any, date]] = []
    dropped: list[Any] = []
    for it in data:
        try:
            d = _item_date(it, date_field)
        except (ValueError, TypeError):
            dropped.append(it)
            continue
        dated.append((it, d))

    if not dated:
        return []

    dated.sort(key=lambda x: x[1])
    buckets: dict[tuple[int, int], list[Any]] = {}
    for it, d in dated:
        buckets.setdefault((d.year, d.month), []).append(it)
    base_month = date(dated[0][1].year, dated[0][1].month, 1)
    global_max = dated[-1][1]

    splits: list[WalkSplit] = []
    i = 0
    # suficiente para cobrir toda a janela de calendario
    max_months = (global_max.year - base_month.year) * 12 + (global_max.month - base_month.month) + 12
    i = train_months
    while True:
        if expanding:
            train_start = base_month
        else:
            train_start = _add_months(base_month, i - train_months)
        test_start_month = _add_months(base_month, i)

        if test_start_month > global_max and i > 0:
            break
        if test_start_month > global_max and not dated:
            break

        # itens do treino cujo mes de calendario cai na janela
        train_candidates = []
        # janela expansiva: todos os meses desde o inicio ate o teste (antes
        # so os primeiros train_months meses entravam, em toda dobra)
        for k in range(i if expanding else train_months):
            ym = _add_months(train_start, k)
            train_candidates.extend(buckets.get((ym.year, ym.month), []))
        test_candidates = []
        for k in range(test_months):
            ym = _add_months(test_start_month, k)
            test_candidates.extend(buckets.get((ym.year, ym.month), []))

        if not test_candidates:
            i += step_months
            continue
        test_min = min(_item_date(it, date_field) for it in test_candidates)
        test_window_start = test_start_month
        cutoff = test_window_start - timedelta(days=purge_days)

        train_items = []
        train_purged: list[Any] = []
        train_id_set = set()
        for it in train_candidates:
            fs = _first_seen_dt(it)
            d = _item_date(it, date_field)
            if fs is None:
                train_purged.append(it)
                continue
            if d <= cutoff and fs <= _normalize_datetime(cutoff):
                train_items.append(it)
                train_id_set.add(id(it))
            else:
                train_purged.append(it)

        test_id_set = {id(it) for it in test_candidates}
        for it, d in dated:
            if id(it) in train_id_set or id(it) in test_id_set:
                continue
            if cutoff < d < test_min and it not in train_purged:
                train_purged.append(it)

        if not train_items:
            i += step_months
            if i > max_months:
                break
            continue
        train_end = max((_item_date(it, date_field) for it in train_items), default=cutoff)
        split = WalkSplit(
            train=list(train_items),
            test=list(test_candidates),
            train_end=train_end,
            test_start=min(_item_date(it, date_field) for it in test_candidates),
            purged=list(train_purged),
            dropped=list(dropped),
        )
        splits.append(split)

        i += step_months
        if i > max_months:
            break

    return splits


class WalkForwardSplitter:
    def __init__(
        self,
        *,
        date_field: str = "start_at",
        train_months: int = 6,
        test_months: int = 3,
        step_months: int = 3,
        purge_days: int = 30,
        expanding: bool = True,
        horizons: Iterable[int] | None = None,
    ) -> None:
        self.date_field = date_field
        self.train_months = train_months
        self.test_months = test_months
        self.step_months = step_months
        self.purge_days = purge_days
        self.expanding = expanding
        self.horizons = horizons

    def split(self, items: Iterable[Any]) -> list[WalkSplit]:
        return walk_forward_splits(
            items,
            date_field=self.date_field,
            train_months=self.train_months,
            test_months=self.test_months,
            step_months=self.step_months,
            purge_days=self.purge_days,
            expanding=self.expanding,
            horizons=self.horizons,
        )

    def __call__(self, items: Iterable[Any]) -> list[WalkSplit]:
        return self.split(items)


# Aliases de compatibilidade
walk_forward_split = walk_forward_splits
walk_forward = walk_forward_splits
split_walk_forward = walk_forward_splits
walkforward_splits = walk_forward_splits
walkforward = walk_forward_splits
purged_walk_forward = walk_forward_splits
time_series_split = walk_forward_splits
WalkForward = WalkForwardSplitter
WorkForwardSplitter = WalkForwardSplitter

__all__ = [
    "WalkForward",
    "WalkForwardSplitter",
    "WalkSplit",
    "WorkForwardSplitter",
    "brier_score",
    "log_loss",
    "metrics",
    "purged_walk_forward",
    "split_walk_forward",
    "time_series_split",
    "walk_forward",
    "walk_forward_split",
    "walk_forward_splits",
    "walkforward",
    "walkforward_splits",
]
