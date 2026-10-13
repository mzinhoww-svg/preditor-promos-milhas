"""Baselines B0 (taxa-base) e B1 (hazard discreto sazonal) para ofertas de pontos/milhas.

API publica:
- ``B0``/``B1``: classes com ``fit`` e ``predict(as_of=..., horizons=...)``.
- ``predict_proba(..., method="b0"|"b1", as_of=..., horizon=...|horizons=...)``.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

HORIZONS_DEFAULT = (7, 15, 30)
TZ = ZoneInfo("America/Sao_Paulo")
WINDOW_DEDUP_DAYS = 3  # mesmo campanha: +/- 3 dias (glossario)
SHRINKAGE_TAU = 30.0


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
                d = date.fromisoformat(value.strip()[:10])
                dt = datetime.combine(d, time.min)
            except ValueError as exc:
                raise ValueError(f"as_of/data invalida: {value!r}") from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    raise ValueError(f"as_of obrigatorio e deve ser data/datetime/ISO: {value!r}")

def _to_date(value: Any) -> date:
    return _normalize_datetime(value).date()

def _to_datetime(value: Any) -> datetime:
    try:
        return _normalize_datetime(value)
    except ValueError:
        return None

def _as_of_date(value: Any) -> date:
    if value is None:
        raise ValueError("as_of e obrigatorio")
    return _to_date(value)


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


def _origin(rec: Any) -> Any:
    return _get(rec, "origin", "origem", default=None)


def _destination(rec: Any) -> Any:
    return _get(rec, "destination", "destino", default=None)


def _event_type(rec: Any) -> Any:
    return _get(rec, "event_type", "type", "tipo", default=None)


def _start(rec: Any) -> date | None:
    v = _get(rec, "start_at", "start", "date", "event_date", default=None)
    try:
        return _to_date(v) if v is not None else None
    except ValueError:
        return None


def _first_seen_dt(rec: Any) -> datetime | None:
    v = _get(rec, "first_seen_at", "first_seen", default=None)
    if v is None:
        return None
    try:
        return _to_datetime(v)
    except ValueError:
        return None


def _matches(
    rec: Any,
    origin: Any = None,
    destination: Any = None,
    event_type: Any = None,
    segmented: Any = None,
    segment_label: Any = None,
) -> bool:
    if origin is not None and _origin(rec) != origin:
        return False
    if destination is not None and _destination(rec) != destination:
        return False
    if event_type is not None and _event_type(rec) != event_type:
        return False
    seg = _get(rec, "segmented", default=False)
    if segmented is None:
        # Geral exclui segmentada por padrao (glossario).
        if seg is True:
            return False
    elif seg is not None and bool(seg) != bool(segmented):
        return False
    return not (segment_label is not None and str(_get(rec, "segment_label", "segment", default="")) != str(segment_label))


def _record_weight(rec: Any) -> float:
    return 1.0


def _available(rec: Any, as_of: date, as_of_dt: datetime) -> bool:
    start = _start(rec)
    if start is None or start > as_of:
        return False
    fs = _first_seen_dt(rec)
    if fs is None:
        return False
    return fs <= as_of_dt


def _filter_history(
    records: Iterable[Any],
    origin: Any = None,
    destination: Any = None,
    event_type: Any = None,
    as_of: Any = None,
    segmented: Any = None,
    segment_label: Any = None,
) -> list[Any]:
    ao = _as_of_date(as_of)
    ao_dt = _to_datetime(as_of)
    out: list[Any] = []
    for r in records or []:
        if not _matches(r, origin, destination, event_type, segmented, segment_label):
            continue
        if not _available(r, ao, ao_dt):
            continue
        out.append(r)
    return out


def _effective_starts(records: Iterable[Any]) -> list[tuple[date, float]]:
    """Agrupa campanhas dentro de +/-3 dias (dedup do glossario) e pondera por weight."""
    ordered = sorted((r for r in records or [] if _start(r) is not None), key=_start)
    clusters: list[tuple[date, float]] = []
    for rec in ordered:
        d = _start(rec)
        assert d is not None
        w = _record_weight(rec)
        if clusters and (d - clusters[-1][0]).days <= WINDOW_DEDUP_DAYS:
            prev_date, prev_w = clusters[-1]
            clusters[-1] = (prev_date, min(1.0, prev_w + w))
        else:
            clusters.append((d, min(1.0, w)))
    return clusters


def _clamp01(x: float) -> float:
    import math

    if math.isnan(x) or math.isinf(x):
        return 0.0
    return max(0.0, min(1.0, float(x)))


@dataclass
class B0:
    records: list[Any] = field(default_factory=list)
    as_of: Any = None

    def fit(self, records: Any = None, *, as_of: Any = None, **kwargs: Any) -> B0:
        recs = records if records is not None else kwargs.get("records", kwargs.get("offers", kwargs.get("data")))
        if recs is None:
            recs = self.records
        if isinstance(recs, (list, tuple, set)):
            self.records = list(recs)
        elif recs is None:
            self.records = []
        else:
            self.records = [recs]
        if as_of is not None:
            self.as_of = as_of
        return self

    def _daily_rate(
        self,
        origin=None,
        destination=None,
        event_type=None,
        as_of=None,
        segmented=None,
        segment_label=None,
        records=None,
    ) -> float:
        raw = as_of if as_of is not None else self.as_of
        if raw is None:
            raise ValueError("as_of e obrigatorio")
        ao = _as_of_date(raw)
        recs_in = self.records if records is None else records
        if isinstance(records, (list, tuple, set)):
            recs_in = list(records)
        recs = _filter_history(
            recs_in or [],
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=raw,
            segmented=segmented,
            segment_label=segment_label,
        )
        starts = _effective_starts(recs)
        if not starts:
            return 0.0
        window_start = starts[0][0]
        window_end = ao if ao >= window_start else starts[-1][0]
        if window_end < window_start:
            window_end = starts[-1][0]
        days = (window_end - window_start).days + 1
        days = max(days, 1)
        total_w = sum(w for _, w in starts)
        rate = total_w / days
        return _clamp01(rate)

    def _probabilities(
        self,
        origin=None,
        destination=None,
        event_type=None,
        as_of=None,
        horizons=HORIZONS_DEFAULT,
        segmented=None,
        segment_label=None,
        records=None,
    ) -> dict[int, float]:
        raw = as_of if as_of is not None else self.as_of
        _as_of_date(raw)
        rate = self._daily_rate(
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=raw,
            segmented=segmented,
            segment_label=segment_label,
            records=records,
        )
        out: dict[int, float] = {}
        for h in horizons:
            h_i = int(h)
            if h_i < 1:
                raise ValueError("horizon deve ser >= 1")
            out[h_i] = _clamp01(1.0 - (1.0 - rate) ** h_i)
        return out

    def predict(self, *args, **kwargs) -> Any:
        origin = kwargs.pop("origin", None)
        destination = kwargs.pop("destination", None)
        event_type = kwargs.pop("event_type", None)
        if args:
            if origin is None and len(args) > 0:
                origin = args[0]
            if destination is None and len(args) > 1:
                destination = args[1]
            if event_type is None and len(args) > 2:
                event_type = args[2]
        segmented = kwargs.pop("segmented", None)
        segment_label = kwargs.pop("segment_label", None)
        records = kwargs.pop("records", kwargs.pop("offers", kwargs.pop("data", None)))
        as_of_raw = kwargs.pop("as_of", None)
        if as_of_raw is None:
            as_of_raw = kwargs.pop("as_of_date", None)
        if as_of_raw is None and self.as_of is not None:
            as_of_raw = self.as_of
        if as_of_raw is None:
            raise ValueError("as_of e obrigatorio")
        raw_as_of = as_of_raw
        if raw_as_of is None:
            raise ValueError("as_of e obrigatorio")
        horizon = kwargs.pop("horizon", kwargs.pop("h", None))
        horizons = kwargs.pop("horizons", None)
        if horizon is not None:
            horizon = int(horizon)
            if horizon < 1:
                raise ValueError("horizon deve ser >= 1")
        if horizons is not None and not isinstance(horizons, (list, tuple)):
            horizons = [int(horizons)]
        recs = self.records if records is None else records
        if isinstance(records, (list, tuple, set)):
            recs = list(records)
        if kwargs:
            raise TypeError(f"argumentos desconhecidos: {sorted(kwargs)}")

        if horizon is not None and horizons is None:
            probs = self._probabilities(
                origin=origin,
                destination=destination,
                event_type=event_type,
                as_of=raw_as_of,
                horizons=(horizon,),
                segmented=segmented,
                segment_label=segment_label,
                records=recs,
            )
            return float(probs[horizon])
        hs = tuple(horizons) if horizons is not None else HORIZONS_DEFAULT
        hs = tuple(int(h) for h in hs)
        for h in hs:
            if h < 1:
                raise ValueError("horizon deve ser >= 1")
        probs = self._probabilities(
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=raw_as_of,
            horizons=hs,
            segmented=segmented,
            segment_label=segment_label,
            records=recs,
        )
        return probs

    def predict_proba(self, *args, **kwargs) -> Any:
        return self.predict(*args, **kwargs)

    probabilities = predict


class B1(B0):
    SHRINKAGE_TAU = SHRINKAGE_TAU

    def _month_rates(
        self,
        origin=None,
        destination=None,
        event_type=None,
        as_of=None,
        segmented=None,
        segment_label=None,
        records=None,
    ) -> tuple[dict[int, float], float]:
        recs_in = self.records if records is None else records
        if isinstance(records, (list, tuple, set)):
            recs_in = list(records)
        _as_of_date(as_of)
        recs = _filter_history(
            recs_in or [],
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=as_of,
            segmented=segmented,
            segment_label=segment_label,
        )
        starts = _effective_starts(recs)
        if not starts:
            return {}, 0.0
        ao = _as_of_date(as_of)
        window_start = starts[0][0]
        window_end = ao if ao >= window_start else starts[-1][0]
        if window_end < window_start:
            window_end = starts[-1][0]
        global_rate = self._daily_rate(
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=window_end,
            segmented=segmented,
            segment_label=segment_label,
            records=recs,
        )
        tau = float(self.SHRINKAGE_TAU)
        rates: dict[int, float] = {}
        for month in range(1, 13):
            month_w = sum(w for d, w in starts if d.month == month)
            obs_days = 0
            cur = window_start
            while cur <= window_end:
                if cur.month == month:
                    obs_days += 1
                cur += timedelta(days=1)
            if obs_days > 0:
                rate = (month_w + tau * global_rate) / (obs_days + tau)
            else:
                rate = global_rate
            rates[month] = _clamp01(rate)
        return rates, global_rate

    def _probabilities(
        self,
        origin=None,
        destination=None,
        event_type=None,
        as_of=None,
        horizons=HORIZONS_DEFAULT,
        segmented=None,
        segment_label=None,
        records=None,
    ) -> dict[int, float]:
        recs_in = self.records if records is None else records
        if isinstance(records, (list, tuple, set)):
            recs_in = list(records)
        raw = as_of if as_of is not None else self.as_of
        ao = _as_of_date(raw)
        recs = _filter_history(
            recs_in or [],
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=raw,
            segmented=segmented,
            segment_label=segment_label,
        )
        starts = _effective_starts(recs)
        if not starts:
            return {int(h): 0.0 for h in horizons}
        rates, global_rate = self._month_rates(
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=raw,
            segmented=segmented,
            segment_label=segment_label,
            records=recs_in,
        )
        out: dict[int, float] = {}
        for h in horizons:
            h_i = int(h)
            if h_i < 1:
                raise ValueError("horizon deve ser >= 1")
            prob_no = 1.0
            for i in range(1, h_i + 1):
                d = ao + timedelta(days=i)
                hr = _clamp01(rates.get(d.month, global_rate))
                prob_no *= (1.0 - hr)
            out[h_i] = _clamp01(1.0 - prob_no)
        return out


def predict_proba(
    records: Any = None,
    origin: Any = None,
    destination: Any = None,
    event_type: Any = None,
    *,
    method: str = "b1",
    model: str | None = None,
    as_of: Any = None,
    horizon: Any = None,
    horizons: Any = None,
    **kwargs: Any,
) -> Any:
    # compatibilidade: permite records como positional unico
    recs_input = records
    if isinstance(records, str) and records in ("b0", "b1"):
        method = records
        recs_input = kwargs.pop("records", kwargs.pop("offers", kwargs.pop("data", None)))
    # kwargs extras de registros
    extra_recs = kwargs.pop("records", kwargs.pop("offers", kwargs.pop("data", None)))
    recs = []
    if recs_input is not None:
        recs.extend(recs_input if isinstance(recs_input, (list, tuple, set)) else [recs_input])
    if extra_recs is not None:
        recs.extend(extra_recs if isinstance(extra_recs, (list, tuple, set)) else [extra_recs])
    # as_of com aliases
    as_of_raw = as_of
    if as_of_raw is None:
        as_of_raw = kwargs.pop("as_of_date", kwargs.pop("cutoff", kwargs.pop("cutoff_date", kwargs.pop("reference_date", kwargs.pop("current_date", None)))))
    if as_of_raw is None:
        raise ValueError("as_of e obrigatorio")
    if kwargs:
        raise TypeError(f"argumentos desconhecidos: {sorted(kwargs)}")
    _as_of_date(as_of_raw)
    name = (model or method or "b1").lower()
    cls = B0 if name in {"b0", "base", "base_rate", "taxa", "taxa_base", "0"} else B1
    m = cls()
    m.fit(recs, as_of=as_of_raw)
    horizon_i = None
    if horizon is not None:
        horizon_i = int(horizon)
        if horizon_i < 1:
            raise ValueError("horizon deve ser >= 1")
    horizons_list = horizons
    if horizons_list is not None and not isinstance(horizons_list, (list, tuple)):
        horizons_list = [int(horizons_list)]
    if horizon_i is not None and horizons_list is None:
        return m.predict(origin, destination, event_type, as_of=as_of_raw, horizon=horizon_i)
    if horizons_list is not None:
        return m.predict(origin, destination, event_type, as_of=as_of_raw, horizons=horizons_list)
    return m.predict(origin, destination, event_type, as_of=as_of_raw, horizons=HORIZONS_DEFAULT)


# Aliases minimos

def base_rate(*args, **kwargs):
    kwargs.setdefault("method", "b0")
    return predict_proba(*args, **kwargs)


def b1_hazard(*args, **kwargs):
    kwargs.setdefault("method", "b1")
    return predict_proba(*args, **kwargs)

b0 = base_rate
b0_rate = base_rate
taxa_base = base_rate


# Aliases de classe
B0Model = B0
B1Model = B1
BaselineB0 = B0
BaselineB1 = B1

__all__ = [
    "B0",
    "B1",
    "HORIZONS_DEFAULT",
    "B0Model",
    "B1Model",
    "BaselineB0",
    "BaselineB1",
    "b1_hazard",
    "base_rate",
    "predict_proba",
]
