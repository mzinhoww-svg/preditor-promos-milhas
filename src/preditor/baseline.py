"""Baselines B0 (taxa-base) e B1 (hazard discreto sazonal) para ofertas de pontos."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

HORIZONS_DEFAULT = (7, 15, 30)


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


def _origin(rec: Any) -> Any:
    return _get(rec, "origin", "origem", "src", default=None)


def _destination(rec: Any) -> Any:
    return _get(rec, "destination", "destino", "dst", default=None)


def _event_type(rec: Any) -> Any:
    return _get(rec, "event_type", "type", "tipo", "offer_type", default=None)


def _segmented(rec: Any) -> Any:
    return _get(rec, "segmented", default=None)


def _segment_label(rec: Any) -> Any:
    return _get(rec, "segment_label", "segment", default=None)


def _start(rec: Any) -> date | None:
    return _to_date(_get(rec, "start_at", "start", "date", "event_date", default=None))


def _first_seen(rec: Any) -> date | None:
    return _to_date(_get(rec, "first_seen_at", "first_seen", default=None))


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
    if segmented is not None and _segmented(rec) is not None and bool(_segmented(rec)) != bool(segmented):
        return False
    return not (segment_label is not None and _segment_label(rec) is not None
               and str(_segment_label(rec)) != str(segment_label))


def _available(rec: Any, cutoff: date) -> bool:
    start = _start(rec)
    if start is None or start > cutoff:
        return False
    fs = _first_seen(rec)
    return not (fs is not None and fs > cutoff)


def _filter_history(
    records: Iterable[Any],
    origin: Any = None,
    destination: Any = None,
    event_type: Any = None,
    as_of: Any = None,
    segmented: Any = None,
    segment_label: Any = None,
) -> list[Any]:
    cutoff = _to_date(as_of)
    if cutoff is None:
        # Sem cutoff, considera tudo (cauda aberta). Limita pelo maximo observado.
        starts = [_start(r) for r in records if _matches(r, origin, destination, event_type, segmented, segment_label)]
        starts = [d for d in starts if d is not None]
        cutoff = max(starts) if starts else date.max
    out = []
    for r in records or []:
        if not _matches(r, origin, destination, event_type, segmented, segment_label):
            continue
        if not _available(r, cutoff):
            continue
        out.append(r)
    return out


def _start_dates(records: Iterable[Any]) -> list[date]:
    return sorted(d for d in (_start(r) for r in records) if d is not None)


def _observed_days(window_start: date, window_end: date, month: int) -> int:
    count = 0
    cur = window_start
    while cur <= window_end:
        if cur.month == month:
            count += 1
        cur += timedelta(days=1)
    return count


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _resolve_as_of(value: Any, fallback_records: list[Any]) -> date:
    d = _to_date(value)
    if d is not None:
        return d
    starts = _start_dates(fallback_records)
    if starts:
        return starts[-1]
    return date.today()


def _resolve_param(kwargs: dict[str, Any], names: list[str], default: Any = None) -> Any:
    for name in names:
        if name in kwargs and kwargs[name] is not None:
            return kwargs.pop(name)
    # pop even if None? leave
    for name in names:
        if name in kwargs:
            return kwargs.pop(name)
    return default


def _resolve_horizon_kwargs(kwargs: dict[str, Any]) -> tuple[int | None, Any]:
    h = _resolve_param(
        kwargs,
        ["horizon", "h", "horizon_days", "horizon_day", "H", "days"],
        None,
    )
    hs = _resolve_param(
        kwargs,
        ["horizons", "horizon_list", "horizons_days", "Hs"],
        None,
    )
    if h is not None:
        try:
            h = int(h)
        except (TypeError, ValueError):
            h = None
    if hs is not None and not isinstance(hs, (list, tuple)):
        try:
            hs = [int(hs)]
        except (TypeError, ValueError):
            hs = None
    return h, hs


def _normalize_records_arg(records: Any, kwargs: dict[str, Any]) -> list[Any]:
    if records is not None:
        if isinstance(records, (list, tuple, set)):
            return list(records)
        return [records]
    for name in ("offers", "data", "dataset", "records", "items", "history"):
        if name in kwargs and kwargs[name] is not None:
            val = kwargs.pop(name)
            if isinstance(val, (list, tuple, set)):
                return list(val)
            return [val]
    return []


@dataclass
class B0:
    """Taxa-base empirica por (par, tipo): probabilidade diaria constante."""

    records: list[Any] = field(default_factory=list)
    as_of: Any = None

    def fit(self, records: Any = None, *, as_of: Any = None, **kwargs) -> B0:
        kw_records = _normalize_records_arg(None, kwargs)
        recs = records if records is not None else (kw_records if kw_records else self.records)
        if isinstance(recs, (list, tuple, set)):
            self.records = list(recs)
        elif recs is None:
            self.records = []
        else:
            self.records = [recs]
        if as_of is not None:
            self.as_of = as_of
        # captura records via kwargs nomeados mesmo se records=None
        extra = _normalize_records_arg(None, kwargs)
        if extra and not self.records:
            self.records = extra
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
        recs_in = self.records if records is None else records
        if isinstance(records, (list, tuple, set)):
            recs_in = list(records)
        recs = _filter_history(
            recs_in or [],
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=as_of if as_of is not None else self.as_of,
            segmented=segmented,
            segment_label=segment_label,
        )
        starts = _start_dates(recs)
        if not starts:
            return 0.0
        cutoff = _resolve_as_of(as_of if as_of is not None else self.as_of, recs)
        window_start = starts[0]
        window_end = cutoff if cutoff >= starts[0] else starts[-1]
        if window_end < window_start:
            window_end = starts[-1]
        days = (window_end - window_start).days + 1
        days = max(days, 1)
        distinct_days = len(set(starts))
        rate = distinct_days / days
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
        recs_in = self.records if records is None else records
        if isinstance(records, (list, tuple, set)):
            recs_in = list(records)
        ao = _resolve_as_of(as_of if as_of is not None else self.as_of, recs_in or [])
        rate = self._daily_rate(
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=ao,
            segmented=segmented,
            segment_label=segment_label,
            records=recs_in,
        )
        out: dict[int, float] = {}
        for h in horizons:
            h = int(h)
            prob_no = (1.0 - rate) ** h
            out[h] = _clamp01(1.0 - prob_no)
        return out

    def predict(self, *args, **kwargs) -> Any:
        # Posicionais: origin, destination, event_type
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
        records = None
        rkw = _normalize_records_arg(None, kwargs)
        if rkw:
            records = rkw
        as_of = _resolve_param(
            kwargs,
            ["as_of", "as_of_date", "cutoff", "cutoff_date", "reference_date", "current_date", "t", "now", "date"],
            None,
        )
        h, hs = _resolve_horizon_kwargs(kwargs)

        recs = self.records if records is None else records
        ao = as_of if as_of is not None else self.as_of

        if h is not None and hs is None:
            probs = self._probabilities(
                origin=origin,
                destination=destination,
                event_type=event_type,
                as_of=ao,
                horizons=(h,),
                segmented=segmented,
                segment_label=segment_label,
                records=recs,
            )
            return float(probs[h])
        horizons = hs if hs is not None else HORIZONS_DEFAULT
        probs = self._probabilities(
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=ao,
            horizons=horizons,
            segmented=segmented,
            segment_label=segment_label,
            records=recs,
        )
        return probs

    def predict_proba(self, *args, **kwargs) -> Any:
        return self.predict(*args, **kwargs)

    # Alias de nomenclatura
    probabilities = predict


class B1(B0):
    """Hazard discreto em tempo por (par, tipo) com ajuste sazonal por mes."""

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
        recs = _filter_history(
            recs_in or [],
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=as_of,
            segmented=segmented,
            segment_label=segment_label,
        )
        starts = _start_dates(recs)
        if not starts:
            return {}, 0.0
        ao = _resolve_as_of(as_of, recs)
        window_start = starts[0]
        window_end = ao if ao >= starts[0] else starts[-1]
        if window_end < window_start:
            window_end = starts[-1]
        global_rate = self._daily_rate(
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=window_end,
            segmented=segmented,
            segment_label=segment_label,
            records=recs_in,
        )
        rates: dict[int, float] = {}
        for month in range(1, 13):
            month_starts = [d for d in starts if d.month == month]
            obs_days = _observed_days(window_start, window_end, month)
            if obs_days > 0:
                distinct = len(set(month_starts))
                rates[month] = _clamp01(distinct / obs_days)
            else:
                rates[month] = global_rate
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
        ao = _resolve_as_of(as_of if as_of is not None else self.as_of, recs_in or [])
        rates, global_rate = self._month_rates(
            origin=origin,
            destination=destination,
            event_type=event_type,
            as_of=ao,
            segmented=segmented,
            segment_label=segment_label,
            records=recs_in,
        )
        if not rates:
            # sem historico: probabilidade zero
            return {int(h): 0.0 for h in horizons}
        out: dict[int, float] = {}
        for h in horizons:
            h = int(h)
            prob_no = 1.0
            for i in range(1, h + 1):
                d = ao + timedelta(days=i)
                hr = rates.get(d.month, global_rate)
                hr = _clamp01(hr)
                prob_no *= (1.0 - hr)
            out[h] = _clamp01(1.0 - prob_no)
        return out


# ---------- Funções de módulo ----------


def _split_horizon_args(
    horizon: Any = None,
    horizons: Any = None,
    **kwargs: Any,
) -> tuple[int | None, Any]:
    return _resolve_horizon_kwargs({"horizon": horizon, "horizons": horizons, **kwargs})


def base_rate(
    records: Any = None,
    origin: Any = None,
    destination: Any = None,
    event_type: Any = None,
    *,
    as_of: Any = None,
    horizon: Any = None,
    horizons: Any = None,
    **kwargs: Any,
) -> Any:
    recs = _normalize_records_arg(records, kwargs)
    ao = as_of
    # records pode ter sido passado por kwargs e removido de kwargs
    m = B0()
    m.fit(recs, as_of=ao)
    h, hs = _resolve_horizon_kwargs({"horizon": horizon, "horizons": horizons, **kwargs})
    if h is not None and hs is None:
        return m.predict(origin, destination, event_type, as_of=ao, horizon=h)
    if hs is not None:
        return m.predict(origin, destination, event_type, as_of=ao, horizons=hs)
    if horizon is None and horizons is None:
        # default: um float se horizon inferido? mantém dict completo
        return m.predict(origin, destination, event_type, as_of=ao, horizons=HORIZONS_DEFAULT)
    return m.predict(origin, destination, event_type, as_of=ao, horizons=HORIZONS_DEFAULT)


def b0(*args: Any, **kwargs: Any) -> Any:
    # Aceita assinatura posicional flexível: (records, origin, dest, type, ...)
    records = kwargs.pop("records", None)
    origin = kwargs.pop("origin", None)
    destination = kwargs.pop("destination", None)
    event_type = kwargs.pop("event_type", None)
    if args:
        # Se primeiro arg é lista/iterável de records
        first = args[0]
        if isinstance(first, (list, tuple, set)) or not isinstance(first, str) and hasattr(first, "__iter__") and not isinstance(first, (str, bytes, dict)):
            records = first
            rest = list(args[1:])
        else:
            rest = list(args)
        if len(rest) > 0 and origin is None:
            origin = rest[0]
        if len(rest) > 1 and destination is None:
            destination = rest[1]
        if len(rest) > 2 and event_type is None:
            event_type = rest[2]
    # as_of
    as_of = kwargs.pop("as_of", None)
    if as_of is None:
        as_of = _resolve_param(kwargs, ["as_of_date", "cutoff", "cutoff_date", "reference_date", "current_date", "t", "now", "date"], None)
    horizon = kwargs.pop("horizon", None)
    if horizon is None:
        horizon = kwargs.pop("h", None)
    horizons = kwargs.pop("horizons", None)
    return base_rate(
        records,
        origin,
        destination,
        event_type,
        as_of=as_of,
        horizon=horizon,
        horizons=horizons,
        **kwargs,
    )


def b1_hazard(*args: Any, **kwargs: Any) -> Any:
    records = kwargs.pop("records", None)
    origin = kwargs.pop("origin", None)
    destination = kwargs.pop("destination", None)
    event_type = kwargs.pop("event_type", None)
    if args:
        first = args[0]
        if isinstance(first, (list, tuple, set)) or (hasattr(first, "__iter__") and not isinstance(first, (str, bytes, dict))):
            records = first
            rest = list(args[1:])
        else:
            rest = list(args)
        if len(rest) > 0 and origin is None:
            origin = rest[0]
        if len(rest) > 1 and destination is None:
            destination = rest[1]
        if len(rest) > 2 and event_type is None:
            event_type = rest[2]
    as_of = kwargs.pop("as_of", None)
    if as_of is None:
        as_of = _resolve_param(kwargs, ["as_of_date", "cutoff", "cutoff_date", "reference_date", "current_date", "t", "now", "date"], None)
    horizon = kwargs.pop("horizon", kwargs.pop("h", None))
    horizons = kwargs.pop("horizons", None)
    recs = _normalize_records_arg(records, kwargs) if records is None else ([records] if not isinstance(records, (list, tuple, set)) else list(records))
    # incluir records passados por kwargs
    extra = _normalize_records_arg(None, kwargs)
    if extra:
        recs = recs + extra
    m = B1()
    m.fit(recs, as_of=as_of)
    if horizon is not None and horizons is None:
        return m.predict(origin, destination, event_type, as_of=as_of, horizon=horizon)
    if horizons is not None:
        return m.predict(origin, destination, event_type, as_of=as_of, horizons=horizons)
    if horizon is None and horizons is None:
        # default: se chamado com horizon implícito? retorna dict completo
        return m.predict(origin, destination, event_type, as_of=as_of, horizons=HORIZONS_DEFAULT)
    return m.predict(origin, destination, event_type, as_of=as_of, horizons=HORIZONS_DEFAULT)


def predict_proba(
    records: Any = None,
    origin: Any = None,
    destination: Any = None,
    event_type: Any = None,
    *,
    as_of: Any = None,
    horizon: Any = None,
    horizons: Any = None,
    method: str = "b1",
    model: str | None = None,
    **kwargs: Any,
) -> Any:
    # Aceita records na primeira posição posicional via args? Esta assinatura posicional records.
    recs = _normalize_records_arg(records, kwargs)
    extra = _normalize_records_arg(None, kwargs)
    if extra:
        recs = recs + extra
    as_of_resolved = as_of
    if as_of_resolved is None:
        as_of_resolved = _resolve_param(kwargs, ["as_of_date", "cutoff", "cutoff_date", "reference_date", "current_date", "t", "now", "date"], None)

    name = (model or method or "b1").lower()
    if name in {"b0", "base", "base_rate", "taxa", "taxa_base", "0"}:
        cls = B0
    else:
        cls = B1
    m = cls()
    m.fit(recs, as_of=as_of_resolved)
    if horizon is not None and horizons is None:
        return m.predict(origin, destination, event_type, as_of=as_of_resolved, horizon=horizon, **kwargs)
    if horizons is not None:
        return m.predict(origin, destination, event_type, as_of=as_of_resolved, horizons=horizons, **kwargs)
    # default completo
    return m.predict(origin, destination, event_type, as_of=as_of_resolved, horizons=HORIZONS_DEFAULT, **kwargs)


# Aliases solicitados/possíveis
b0_rate = base_rate
taxa_base = base_rate
b1 = b1_hazard
hazard = b1_hazard
hazard_proba = b1_hazard
predict = predict_proba
predict_probability = predict_proba
probability = predict_proba

B0Model = B0
B1Model = B1
BaselineB0 = B0
BaselineB1 = B1
BaseRate = B0
BaseRateModel = B0
Hazard = B1
HazardModel = B1
DiscreteHazard = B1
SeasonalHazard = B1
TaxaBaseModel = B0

# Permitir chamada estilo b0(records, origin, ...) posicional já coberta acima.
# Exportar tudo
__all__ = [
    "B0",
    "B1",
    "HORIZONS_DEFAULT",
    "B0Model",
    "B1Model",
    "BaseRate",
    "BaseRateModel",
    "BaselineB0",
    "BaselineB1",
    "DiscreteHazard",
    "Hazard",
    "HazardModel",
    "SeasonalHazard",
    "TaxaBaseModel",
    "b0",
    "b0_rate",
    "b1",
    "b1_hazard",
    "base_rate",
    "hazard",
    "hazard_proba",
    "predict",
    "predict_proba",
    "predict_probability",
    "probability",
    "taxa_base",
]
