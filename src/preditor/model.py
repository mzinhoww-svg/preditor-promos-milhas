"""Modelo C1 (LightGBM global pessoa-dia), grade diária, bootstrap em blocos e decisão campeão x desafiante."""

from __future__ import annotations

import os
import random
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, ClassVar

import lightgbm as lgb
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from preditor.baseline import HORIZONS_DEFAULT as _BASE_H
from preditor.baseline import TZ as _BASE_TZ
from preditor.calendar_seed import SEED_EVENTS, seed_calendar_events

HORIZONS_DEFAULT = tuple(_BASE_H)
TZ = _BASE_TZ

# ---------------------------------------------------------------------------
# helpers de data
# ---------------------------------------------------------------------------


def _norm_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=TZ)
        return value.astimezone(TZ)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=TZ)
    if isinstance(value, str):
        txt = value.strip()
        try:
            dt = datetime.fromisoformat(txt)
        except ValueError:
            dt = datetime.combine(date.fromisoformat(txt[:10]), time.min)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    raise ValueError(f"as_of/data invalida: {value!r}")


def _to_date(value: Any) -> date:
    return _norm_dt(value).date()


def _first_seen_dt(value: Any) -> datetime | None:
    # Aceita tanto um registro (dict/objeto) quanto o valor direto de
    # first_seen_at, espelhando a semantica de baseline._first_seen_dt.
    # Em registros extrai o campo (falha fechada quando ausente/invalido).
    if isinstance(value, dict):
        if "first_seen_at" in value or "first_seen" in value:
            value = _get(value, "first_seen_at", "first_seen", default=None)
        # se nao tem o campo, nao inventa data (permanece None)
        else:
            value = None
    elif hasattr(value, "first_seen_at") or hasattr(value, "first_seen"):
        attr = "first_seen_at" if hasattr(value, "first_seen_at") else "first_seen"
        value = getattr(value, attr, None)
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            return _norm_dt(value)
        if isinstance(value, date):
            # data sem hora: fim do dia (conservador point-in-time)
            return datetime.combine(value, time.max, tzinfo=TZ)
        txt = str(value).strip()
        if "T" not in txt and " " not in txt:
            return datetime.combine(date.fromisoformat(txt[:10]), time.max, tzinfo=TZ)
        return _norm_dt(txt)
    except (ValueError, TypeError):
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


def _origin(rec):
    return _get(rec, "origin", "origem", default=None)


def _destination(rec):
    return _get(rec, "destination", "destino", default=None)


def _event_type(rec):
    return _get(rec, "event_type", "type", "tipo", default=None)


def _start(rec):
    v = _get(rec, "start_at", "start", "date", "event_date", default=None)
    try:
        return _to_date(v) if v is not None else None
    except ValueError:
        return None


AS_OF_ALIASES = (
    "as_of",
    "as_of_date",
    "cutoff",
    "cutoff_date",
    "reference_date",
    "current_date",
    "t",
)

# ---------------------------------------------------------------------------
# Grade diária
# ---------------------------------------------------------------------------


def _pairs_types(records: Iterable[Any]):
    pairs = set()
    types = set()
    for r in records or []:
        pairs.add((_origin(r), _destination(r)))
        types.add(_event_type(r))
    return pairs, types


def build_daily_grade(
    records: Iterable[Any] | None = None,
    *,
    offers: Iterable[Any] | None = None,
    data: Iterable[Any] | None = None,
    horizons: Iterable[int] | None = None,
    start_date: Any = None,
    end_date: Any = None,
    pairs: Iterable[tuple[Any, Any]] | None = None,
    event_types: Iterable[Any] | None = None,
    types: Iterable[Any] | None = None,
    as_of: Any = None,
    embargo_cutoff: Any = None,
    cutoff: Any = None,
    t_values: Iterable[Any] | None = None,
    include_features: bool = True,
    calendar_events: Iterable[Any] | None = None,
    sibling_offers: Iterable[Any] | None = None,
) -> list[dict[str, Any]]:
    """Gera grade diária de instantes (par, tipo, t, h) com rótulo y(t,h).

    y(t,h)=1 se existir oferta do par/tipo com início em [t+1, t+h].
    """
    recs = records if records is not None else (offers if offers is not None else data)
    recs = list(recs or [])
    hs = list(horizons) if horizons is not None else list(HORIZONS_DEFAULT)
    hs = [int(h) for h in hs]
    if not hs:
        hs = list(HORIZONS_DEFAULT)
    cal = list(calendar_events) if calendar_events is not None else None
    if types is None and event_types is None:
        # optional
        pass
    type_filter = event_types if event_types is not None else types

    # pares/tipos
    if pairs is None:
        pp, tt = _pairs_types(recs)
    else:
        pp = {tuple(p) for p in pairs}
        tt = set(types or type_filter or []) if (types or type_filter) else None
    if tt is None:
        if type_filter is not None:
            tt = set(type_filter)
        else:
            _, tt = _pairs_types(recs)
    if not tt:
        tt = {None}

    # datas
    if start_date is None:
        starts = [_start(r) for r in recs if _start(r) is not None]
        if starts:
            start_date = min(starts)
        else:
            start_date = date.today() if False else date(2024, 1, 1)
    if end_date is None:
        starts = [_start(r) for r in recs if _start(r) is not None]
        if starts:
            end_date = max(starts)
        else:
            end_date = _to_date(start_date)
    start_d = _to_date(start_date)
    end_d = _to_date(end_date)
    if t_values is not None:
        day_list = [_to_date(t) for t in t_values]
    else:
        day_list = [
            start_d + timedelta(days=i) for i in range((end_d - start_d).days + 1)
        ]

    cutoff_dt = None
    if embargo_cutoff is not None or cutoff is not None:
        cutoff_dt = _to_date(embargo_cutoff if embargo_cutoff is not None else cutoff)

    # index offers by pair/type for fast label
    offers_by_pair_type = defaultdict(list)
    for r in recs:
        offers_by_pair_type[(_origin(r), _destination(r), _event_type(r))].append(r)

    sibling_groups = defaultdict(list)
    for r in recs:
        sibling_groups[(_origin(r), _destination(r))].append(r)

    grade_rows: list[dict[str, Any]] = []
    for t in day_list:
        t_dt = datetime.combine(t, time.min, tzinfo=TZ)
        for o, d in pp:
            for tp in tt:
                key = (o, d, tp)
                # point-in-time known by first_seen_at
                known = (
                    [
                        r
                        for r in offers_by_pair_type.get(key, [])
                        if (_fs := _first_seen_dt(r)) is not None and _fs <= t_dt
                    ]
                    if include_features
                    else []
                )
                for h in hs:
                    if cutoff_dt is not None and t + timedelta(days=h) > cutoff_dt:
                        # embargo: janela de rótulo cruza corte
                        continue
                    # label
                    y = 0
                    lo = t + timedelta(days=1)
                    hi = t + timedelta(days=h)
                    for r in offers_by_pair_type.get(key, []):
                        sd = _start(r)
                        if sd is not None and lo <= sd <= hi:
                            # para rótulo, evento futuro permitido; mas supervisão usa real
                            y = 1
                            break
                    row = {
                        "origin": o,
                        "destination": d,
                        "event_type": tp,
                        "t": t,
                        "h": h,
                        "horizon": h,
                        "y": int(y),
                        "label": int(y),
                    }
                    if include_features:
                        # features point-in-time
                        rows_feats = _features_for_example(
                            o, d, tp, t, recs, known, cal, hs
                        )
                        row.update(rows_feats)
                    grade_rows.append(row)
    return grade_rows


def _features_for_example(
    origin, destination, event_type, t, all_recs, known_recs, cal, horizons
):
    t_dt = datetime.combine(t, time.min, tzinfo=TZ)
    # days since last offer
    last_start = None
    for r in known_recs:
        sd = _start(r)
        if sd is not None and sd <= t and (last_start is None or sd > last_start):
            last_start = sd
    days_since = (t - last_start).days if last_start is not None else 999

    # ofertas recentes pares irmaos (ultimos 7/30 dias)
    siblings = 0
    siblings7 = 0
    siblings30 = 0
    for r in all_recs:
        if _origin(r) == origin and _destination(r) == destination:
            continue
        fs = _first_seen_dt(r)
        sd = _start(r)
        if fs is not None and fs <= t_dt:
            if sd is not None and t - timedelta(days=30) <= sd <= t:
                siblings30 += 1
            if sd is not None and t - timedelta(days=7) <= sd <= t:
                siblings7 += 1
            if sd is not None and t - timedelta(days=30) <= sd <= t:
                siblings += 1

    # calendar
    cal_names = []
    days_to_next_event = 999
    is_event_day = 0
    if cal is not None:
        for e in cal:
            ed = (
                e.get("event_date")
                if isinstance(e, dict)
                else getattr(e, "event_date", None)
            )
            if ed is None:
                continue
            try:
                edd = _to_date(ed)
            except (ValueError, TypeError):
                continue
            if edd == t:
                is_event_day = 1
                nm = e.get("name") if isinstance(e, dict) else getattr(e, "name", None)
                cal_names.append(nm)
            if edd >= t:
                dd = (edd - t).days
                days_to_next_event = min(days_to_next_event, dd)
    if days_to_next_event == 999:
        days_to_next_event = -1

    return {
        "days_since_last_offer": int(days_since),
        "month": int(t.month),
        "day_of_week": int(t.weekday()),
        "sibling_offers_7d": int(siblings7),
        "sibling_offers_30d": int(siblings30),
        "sibling_offers": int(siblings),
        "is_calendar_event_day": int(is_event_day),
        "days_to_next_calendar_event": int(days_to_next_event),
        "n_known_offers": len(known_recs),
    }


# Aliases
daily_grade = build_daily_grade
make_daily_grade = build_daily_grade
GradeBuilder = build_daily_grade
build_grade = build_daily_grade
grade_diaria = build_daily_grade

# ---------------------------------------------------------------------------
# C1 LightGBM
# ---------------------------------------------------------------------------


def _available_offers(recs, t):
    t_dt = (
        datetime.combine(t, time.min, tzinfo=TZ)
        if isinstance(t, date) and not isinstance(t, datetime)
        else _norm_dt(t)
    )
    out = []
    for r in recs or []:
        fs = _first_seen_dt(r)
        if fs is not None and fs <= t_dt:
            out.append(r)
    return out


CAL_FEATURES_NAMES = None


@dataclass
class C1:
    horizons: tuple[int, ...] = tuple(HORIZONS_DEFAULT)
    calibration: str = "isotonic"  # isotonic | platt
    calendar_events: list[Any] = field(default_factory=list)
    random_state: int = 42
    models: dict[int, Any] = field(default_factory=dict)
    calibrators: dict[int, Any] = field(default_factory=dict)
    encoders: dict[str, dict[Any, int]] = field(default_factory=dict)
    trained: bool = False
    feature_names: list[str] = field(default_factory=list)
    base_rate_: float = 0.0
    records: list = field(default_factory=list)
    as_of: Any = None
    calibration_info: dict[str, Any] = field(default_factory=dict)
    calibration_booster: dict[int, Any] = field(default_factory=dict)

    MIN_CALIB_ROWS: ClassVar[int] = 30
    PROB_MIN: ClassVar[float] = 0.01
    PROB_MAX: ClassVar[float] = 0.99
    FEATURE_NAMES: ClassVar[tuple[str, ...]] = (
        "origin",
        "destination",
        "event_type",
        "days_since_last_offer",
        "month",
        "day_of_week",
        "sibling_offers_7d",
        "sibling_offers_30d",
        "is_calendar_event_day",
        "days_to_next_calendar_event",
        "n_known_offers",
        "h",
    )
    LGB_PARAMS: ClassVar[dict[str, Any]] = {
        "objective": "binary",
        "metric": "binary_logloss",
        "verbosity": -1,
        "num_leaves": 31,
        "min_child_samples": 20,
        "learning_rate": 0.05,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 1,
    }

    def __post_init__(self):
        self.feature_names = list(self.FEATURE_NAMES)
        if not self.calendar_events:
            self.calendar_events = [
                {"name": n, "kind": k, "event_date": d} for (n, k, d) in SEED_EVENTS
            ]

    # feature encoding helpers
    def _encode(self, col, values, fit=False):
        if fit:
            uniq = sorted(set(values), key=lambda x: str(x))
            self.encoders[col] = {v: i for i, v in enumerate(uniq)}
        enc = self.encoders.get(col, {})
        out = []
        for v in values:
            out.append(enc.get(v, -1))
        return out

    def _rows_to_Xy(self, grade_rows, h, fit=False):
        # filter rows where h matches
        rows = [r for r in grade_rows if int(r.get("h", r.get("horizon", 0))) == int(h)]
        if not rows:
            rows = [r for r in grade_rows]  # fallback
        # if grade contains multiple h but row h differs, still use label y? We'll trust
        feature_names = list(self.FEATURE_NAMES)
        self.feature_names = feature_names
        cat_cols = {"origin", "destination", "event_type"}
        # encode categoricals
        col_values = {
            c: [r.get(c) for r in rows] for c in feature_names if c in cat_cols
        }
        if fit:
            for c in cat_cols:
                self._encode(c, col_values[c], fit=True)
        # origins dest combos
        X = []
        for r in rows:
            vals = []
            for c in feature_names:
                if c in cat_cols:
                    enc = self.encoders.get(c, {})
                    vals.append(
                        enc.get(
                            r.get(c),
                            None,
                        )
                        if r.get(c) in enc
                        else enc.get(r.get(c), -1)
                    )
                elif c == "h":
                    vals.append(int(r.get("h", r.get("horizon", h))))
                else:
                    v = r.get(c, 0)
                    if v is None:
                        v = 0
                    vals.append(v)
            X.append(vals)
        X = np.asarray(X, dtype=float)
        y = np.asarray([int(r.get("y", r.get("label", 0))) for r in rows], dtype=int)
        cat_idxs = [feature_names.index(c) for c in cat_cols]
        return X, y, cat_idxs, feature_names, rows

    def fit(self, *args, **kwargs):
        # acepta records/grade/as_of
        records = kwargs.pop("records", kwargs.pop("offers", kwargs.pop("data", None)))
        grade = kwargs.pop("grade", kwargs.pop("dataset", kwargs.pop("rows", None)))
        horizons = kwargs.pop("horizons", None)
        as_of = kwargs.pop("as_of", None)
        for a in args:
            if (
                isinstance(a, (list, tuple))
                and a
                and isinstance(a[0], dict)
                and "t" in a[0]
                and "h" in a[0]
            ):
                grade = a
            elif isinstance(a, (list, tuple)):
                records = a
            elif isinstance(a, (int,)):
                pass
        if horizons is not None:
            self.horizons = tuple(
                int(h)
                for h in (horizons if not isinstance(horizons, int) else [horizons])
            )
        if records is None and grade is None:
            # maybe first positional is records already
            pass
        if as_of is not None:
            _ao = _norm_dt(as_of)
            if records is not None:
                records = [
                    r
                    for r in list(records)
                    if (_first_seen_dt(r) is not None and _first_seen_dt(r) <= _ao)
                ]
        if grade is None:
            # build grade from records
            if records is None:
                records = []
            embargo = as_of if as_of is not None else self.as_of
            grade = build_daily_grade(
                records,
                horizons=self.horizons,
                include_features=True,
                calendar_events=self.calendar_events,
                embargo_cutoff=embargo,
            )
        grade = list(grade or [])
        if records is not None:
            self.records = list(
                records if not isinstance(records, (set,)) else list(records)
            )
        if as_of is not None:
            self.as_of = as_of
        if len(grade) < 5:
            # tiny: add minimal placeholders? Just store base rate
            ys = [int(r.get("y", r.get("label", 0))) for r in grade]
            self.base_rate_ = float(np.mean(ys)) if ys else 0.0
            self.trained = False
            return self

        # Split temporal com purge: a fatia de calibracao so comeca
        # max(h) dias depois do fim do treino (rotulos nao se sobrepoem).
        max_h = max(int(h) for h in self.horizons)
        ts = sorted({_to_date(r.get("t")) for r in grade})
        cut_t = ts[max(0, int(len(ts) * 0.8) - 1)]
        calib_start = cut_t + timedelta(days=max_h)
        train_rows = [r for r in grade if _to_date(r.get("t")) <= cut_t]
        val_rows = [r for r in grade if _to_date(r.get("t")) >= calib_start]
        self.calibration_info = {
            "purge_days": max_h,
            "train_max_t": max(_to_date(r.get("t")) for r in train_rows),
            "calib_min_t": (
                min(_to_date(r.get("t")) for r in val_rows) if val_rows else None
            ),
            "n_train": len(train_rows),
            "n_calib": len(val_rows),
        }
        self.calibration_booster = {}

        # base rate
        ys_all = [int(r.get("y", r.get("label", 0))) for r in grade]
        self.base_rate_ = float(np.mean(ys_all)) if ys_all else 0.0

        for h in self.horizons:
            h = int(h)
            Xtr, ytr, cat_idxs, fn, _ = self._rows_to_Xy(train_rows, h, fit=True)
            if len(set(ytr.tolist())) < 2:
                self.models[h] = None
                self.calibrators[h] = None
                continue
            dtrain = lgb.Dataset(
                Xtr,
                label=ytr,
                categorical_feature=cat_idxs,
                feature_name=fn,
                free_raw_data=False,
            )
            params = dict(self.LGB_PARAMS, seed=self.random_state)
            booster = lgb.train(
                params,
                dtrain,
                num_boost_round=100,
                callbacks=[lgb.log_evaluation(period=0)],
            )
            self.models[h] = booster
            self.calibrators[h] = None
            if not val_rows:
                continue
            Xval, yval, _, _, _ = self._rows_to_Xy(val_rows, h, fit=False)
            if len(yval) < self.MIN_CALIB_ROWS or len(set(yval.tolist())) < 2:
                continue  # fatia pequena/sem variacao: nao calibra (nao inventa)
            raw_val = np.asarray(booster.predict(Xval), dtype=float)
            clipped = np.clip(raw_val, 1e-6, 1 - 1e-6)
            if self.calibration == "platt":
                lr = LogisticRegression(max_iter=1000)
                lr.fit(clipped.reshape(-1, 1), yval)
                cal = ("platt", lr)
            else:
                iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
                iso.fit(clipped, yval)
                cal = ("isotonic", iso)
            self.calibrators[h] = cal
            # o booster que gerou as predicoes de calibracao e o mesmo de models[h]
            self.calibration_booster[h] = booster

        self.trained = True
        return self

    def _calibrate(self, h, raw):
        cal = self.calibrators.get(h)
        raw = np.asarray(raw, dtype=float)
        if cal is None:
            return np.clip(raw, 0.0, 1.0)
        kind, obj = cal
        clipped = np.clip(raw, 1e-6, 1 - 1e-6)
        if kind == "platt":
            return obj.predict_proba(clipped.reshape(-1, 1))[:, 1]
        return np.clip(obj.transform(clipped), 0.0, 1.0)

    def _feature_row(self, origin, destination, event_type, t, records):
        t_d = _to_date(t)
        known = _available_offers(records, t_d)
        same = [
            r
            for r in known
            if _origin(r) == origin
            and _destination(r) == destination
            and _event_type(r) == event_type
        ]
        feats = _features_for_example(
            origin,
            destination,
            event_type,
            t_d,
            list(records or []),
            same,
            self.calendar_events,
            self.horizons,
        )
        # normalize unknown future? known already filtered
        # Build X in feature_names order
        row_vals = []
        for c in self.feature_names:
            if c == "origin":
                row_vals.append(origin)
            elif c == "destination":
                row_vals.append(destination)
            elif c == "event_type":
                row_vals.append(event_type)
            elif c == "h":
                row_vals.append(None)
            else:
                row_vals.append(feats.get(c, 0))
        return row_vals, known

    def predict(self, *args, **kwargs):
        # parse as_of to decide cached engine
        # copy kwargs
        kw = dict(kwargs)
        origin = kw.get("origin", None)
        destination = kw.get("destination", None)
        event_type = kw.get("event_type", None)
        # positional records
        recs = kw.pop("records", kw.pop("offers", kw.pop("data", None)))
        # also support pass records through args? not needed
        as_of_raw = None
        for a in AS_OF_ALIASES:
            if a in kw:
                as_of_raw = kw.pop(a)
                break
        # if not provided, use self.as_of
        if as_of_raw is None:
            as_of_raw = self.as_of
        # rest as original args
        # Determine recs base
        base_recs = recs if recs is not None else (self.records or [])
        if isinstance(base_recs, (list, tuple, set)):
            base_recs = list(base_recs)
        if as_of_raw is None:
            # fallback: use stored model
            kw2 = dict(kw)
            kw2.update({"records": base_recs})
            if origin is not None:
                kw2["origin"] = origin
            if destination is not None:
                kw2["destination"] = destination
            if event_type is not None:
                kw2["event_type"] = event_type
            # reconstruct minimal? easier delegate
            return self._predict_trained(*args, **kwargs)
        as_of_date = _to_date(as_of_raw)
        # records known by as_of
        known_recs = [
            r
            for r in base_recs
            if (
                _first_seen_dt(r) is not None
                and _first_seen_dt(r) <= _norm_dt(as_of_raw)
            )
        ]
        # if stored model compatible (as_of matches and trained), use it
        if (
            self.trained
            and self.as_of is not None
            and _to_date(self.as_of) == as_of_date
            and self.records == known_recs
        ):
            kw2 = dict(kw)
            # inject parsed
            if origin is not None:
                kw2["origin"] = origin
            if destination is not None:
                kw2["destination"] = destination
            if event_type is not None:
                kw2["event_type"] = event_type
            kw2["records"] = base_recs
            # put as_of alias expected by _predict_trained
            kw2["as_of"] = as_of_raw
            if "origin" not in kw2 and origin is None:
                pass
            # call original parser via kwargs; pass through original args
            return self._predict_trained(*args, **kw2)
        # otherwise train temporary engine (point-in-time safe)
        engine = C1(
            horizons=self.horizons,
            calibration=self.calibration,
            calendar_events=self.calendar_events,
            random_state=self.random_state,
        )
        engine.fit(known_recs, as_of=as_of_raw, horizons=self.horizons)
        # call internal trained prediction (no auto-training)
        kw2 = dict(kw)
        if origin is not None:
            kw2["origin"] = origin
        if destination is not None:
            kw2["destination"] = destination
        if event_type is not None:
            kw2["event_type"] = event_type
        kw2["records"] = known_recs
        kw2["as_of"] = as_of_raw
        return engine._predict_trained(*args, **kw2)

    def _predict_trained(self, *args, **kwargs):
        # parse like baseline
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
        records = kwargs.pop("records", kwargs.pop("offers", kwargs.pop("data", None)))
        as_of_raw = None
        for a in AS_OF_ALIASES:
            if a in kwargs:
                as_of_raw = kwargs.pop(a)
                break
        if as_of_raw is None:
            as_of_raw = self.as_of if hasattr(self, "as_of") else None
        if as_of_raw is None:
            raise ValueError("as_of e obrigatorio")
        _to_date(as_of_raw)
        horizon = kwargs.pop("horizon", kwargs.pop("h", None))
        horizons = kwargs.pop("horizons", kwargs.pop("H", None))
        # records fallback
        recs_in = records if records is not None else getattr(self, "records", [])
        if isinstance(records, (list, tuple, set)):
            recs_in = list(records)
        # restrict offers known as of
        recs_in = list(recs_in or [])

        as_of_date = _to_date(as_of_raw)
        single_horizon = None
        if horizon is not None:
            single_horizon = int(horizon)
        hs = None
        if horizons is not None:
            hs = [
                int(h)
                for h in (horizons if not isinstance(horizons, (int,)) else [horizons])
            ]
        if single_horizon is not None and horizons is None:
            hs = [single_horizon]

        if hs is None:
            hs = list(self.horizons)

        for h in hs:
            if h < 1:
                raise ValueError("horizon deve ser >= 1")
        curve = self.predict_curve(origin, destination, event_type, as_of_date, recs_in)
        missing = [h for h in hs if h not in curve]
        if missing:
            raise ValueError(
                f"horizonte(s) {missing} fora de self.horizons={list(self.horizons)}"
            )
        out = {h: curve[h] for h in hs}
        if single_horizon is not None and horizons is None and horizon is not None:
            return out[single_horizon]
        if len(out) == 1 and horizon is not None:
            return float(next(iter(out.values())))
        return out

    def predict_curve(self, origin, destination, event_type, as_of, records):
        """P(evento em <=h dias) para todos os self.horizons, sem retreinar.

        Calibra, aplica o max acumulado sobre TODOS os horizontes do modelo e
        so entao limita a [PROB_MIN, PROB_MAX]; o pedido do chamador apenas
        filtra a saida (a curva nao depende de quais h foram pedidos).
        """
        as_of_date = _to_date(as_of)
        recs = list(records or [])
        raw_by_h: dict[int, float] = {}
        row_vals = None
        for h in sorted(int(x) for x in self.horizons):
            if not self.trained or self.models.get(h) is None:
                raw_by_h[h] = self.base_rate_
                continue
            if row_vals is None:
                row_vals, _known = self._feature_row(
                    origin, destination, event_type, as_of_date, recs
                )
            cat_cols = {"origin", "destination", "event_type"}
            enc_row = []
            for idx, c in enumerate(self.feature_names):
                if c in cat_cols:
                    enc_row.append(self.encoders.get(c, {}).get(row_vals[idx], -1))
                elif c == "h":
                    enc_row.append(h)
                else:
                    v = row_vals[idx]
                    enc_row.append(0 if v is None else v)
            X = np.asarray([enc_row], dtype=float)
            raw = np.atleast_1d(self.models[h].predict(X)).astype(float)
            raw_by_h[h] = float(self._calibrate(h, raw)[0])
        out: dict[int, float] = {}
        prev = 0.0
        for h in sorted(raw_by_h):
            prev = max(prev, raw_by_h[h])
            out[h] = float(min(self.PROB_MAX, max(self.PROB_MIN, prev)))
        return out

    def predict_trained_at(self, origin, destination, event_type, as_of, records, horizons):
        """Predicao no instante `as_of` com o modelo ja treinado (sem retreino).

        Usa so registros com first_seen_at <= as_of (point-in-time).
        """
        t_dt = _norm_dt(_to_date(as_of))
        known = [
            r for r in records or [] if (fs := _first_seen_dt(r)) is not None and fs <= t_dt
        ]
        curve = self.predict_curve(origin, destination, event_type, as_of, known)
        return {int(h): curve[int(h)] for h in horizons}

    def predict_proba(self, *args, **kwargs):
        return self.predict(*args, **kwargs)

    def fit_from_grade(self, *a, **k):
        return self.fit(*a, **k)


C1Model = C1
ChallengerC1 = C1
LightGBMGlobal = C1
LightGBMModel = C1
C1Global = C1

# ---------------------------------------------------------------------------
# Bootstrap em blocos
# ---------------------------------------------------------------------------


def _metric_diffBootstrap(
    metric_fn, y_true, pred_a, pred_b, blocks, n_boot=1000, seed=42, alpha=0.05
):
    rng = random.Random(seed)
    y = np.asarray(y_true, dtype=float)
    pa = np.asarray(pred_a, dtype=float)
    pb = np.asarray(pred_b, dtype=float)
    blocks = np.asarray(blocks)
    unique_blocks = sorted(
        set(blocks.tolist() if hasattr(blocks, "tolist") else list(blocks))
    )
    # block -> indices
    block_to_idx = {b: np.where(blocks == b)[0] for b in unique_blocks}
    n = len(unique_blocks)
    diffs = []
    for _ in range(n_boot):
        chosen = [rng.choice(unique_blocks) for _ in range(n)]
        idx = (
            np.concatenate([block_to_idx[b] for b in chosen])
            if chosen
            else np.array([], dtype=int)
        )
        if len(idx) == 0:
            diffs.append(0.0)
            continue
        ma = metric_fn(y[idx], pa[idx])
        mb = metric_fn(y[idx], pb[idx])
        diffs.append(float(ma - mb))
    diffs = np.asarray(diffs, dtype=float)
    lo = float(np.quantile(diffs, alpha / 2))
    hi = float(np.quantile(diffs, 1 - alpha / 2))
    return {
        "mean": float(np.mean(diffs)),
        "median": float(np.median(diffs)),
        "ci_low": lo,
        "ci_high": hi,
        "excludes_zero": bool(lo > 0 or hi < 0),
        "n_boot": n_boot,
        "n_blocks": n,
        "alpha": alpha,
        "diffs": diffs.tolist(),
    }


def _brier(y, p):
    from preditor.walkforward import brier_score

    return brier_score(
        y.tolist() if hasattr(y, "tolist") else list(y),
        p.tolist() if hasattr(p, "tolist") else list(p),
    )


def _logloss(y, p):
    from preditor.walkforward import log_loss

    return log_loss(
        y.tolist() if hasattr(y, "tolist") else list(y),
        p.tolist() if hasattr(p, "tolist") else list(p),
    )


def block_bootstrap_ci(
    y_true,
    pred_b1,
    pred_c1,
    blocks=None,
    *,
    metric: str = "brier",
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """IC por bootstrap em blocos temporais da diferença métrica(B1) - métrica(C1).

    Diferença > 0 significa que C1 é melhor (menor erro). `blocks` é
    obrigatório e explícito (ex.: semana ISO de t): reamostrar por índice
    quebraria a dependência temporal e a correlação entre pares/tipos.
    """
    if blocks is None:
        raise ValueError(
            "blocks e obrigatorio: informe o bloco temporal (ex.: semana ISO de t)"
        )
    y = np.asarray(y_true)
    pb = np.asarray(pred_b1, dtype=float)
    pc = np.asarray(pred_c1, dtype=float)
    blk = np.asarray(blocks)
    if not (len(y) == len(pb) == len(pc) == len(blk)):
        raise ValueError("y_true, pred_b1, pred_c1 e blocks devem ter o mesmo tamanho")
    if len(y) == 0:
        raise ValueError("dados insuficientes para bootstrap")
    if metric in ("log_loss", "logloss", "nll"):
        metric_fn = _logloss
    elif metric == "brier":
        metric_fn = _brier
    else:
        raise ValueError(f"metric desconhecida: {metric!r}")
    return _metric_diffBootstrap(
        metric_fn, y, pb, pc, blk, n_boot=int(n_boot), seed=int(seed), alpha=float(alpha)
    )


bootstrap_ci = block_bootstrap_ci
bootstrap_block_ci = block_bootstrap_ci
block_bootstrap = block_bootstrap_ci
bloco_bootstrap = block_bootstrap_ci
bootstrap_diferenca = block_bootstrap_ci

# ---------------------------------------------------------------------------
# Calibração / confiabilidade
# ---------------------------------------------------------------------------


def reliability_curve(y_true, y_pred, *, n_bins=10):
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    out = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (p >= lo) & (p < hi) if i < n_bins - 1 else (p >= lo) & (p <= hi)
        if i == n_bins - 1:
            mask = (p >= lo) & (p <= hi)
        if mask.sum() == 0:
            continue
        out.append(
            {
                "bin_low": float(lo),
                "bin_high": float(hi),
                "p_mean": float(np.mean(p[mask])),
                "observed": float(np.mean(y[mask])),
                "n": int(mask.sum()),
            }
        )
    return out


def is_calibrated(y_true, y_pred, *, tol=0.1, min_n=20):
    pts = reliability_curve(y_true, y_pred)
    if not pts:
        return False
    # weighted mean abs error between predicted and observed
    errs = [abs(b["p_mean"] - b["observed"]) * b["n"] for b in pts]
    n = sum(b["n"] for b in pts)
    if n < min_n:
        return False
    wmae = sum(errs) / n
    return bool(wmae <= tol)


# ---------------------------------------------------------------------------
# Decisão campeão x desafiante
# ---------------------------------------------------------------------------


MIN_CAMPAIGNS_PER_PAIR_TYPE = 25
DATA_SOURCES = ("real", "synthetic")


def decide_champion(
    *,
    n_campaigns_by_pair_type: dict[tuple[str, str, str], int],
    data_source: str,
    champion_name: str = "B1",
    challenger_name: str = "C1",
    champion_metrics: dict[str, Any] | None = None,
    challenger_metrics: dict[str, Any] | None = None,
    b1_metrics: dict[str, Any] | None = None,
    c1_metrics: dict[str, Any] | None = None,
    bootstrap_ci_brier: dict[str, Any] | None = None,
    bootstrap_ci_logloss: dict[str, Any] | None = None,
    ci_brier: dict[str, Any] | None = None,
    ci_logloss: dict[str, Any] | None = None,
    ci: dict[str, Any] | None = None,
    reliability: Any = None,
    challenger_calibrated: bool | None = None,
) -> dict[str, Any]:
    """Decide campeão × desafiante. Falha fechada em tudo que falta.

    Promove só se: dados reais, >= 25 campanhas por (par, tipo), C1 menor em
    Brier e log-loss, IC (bloco) favorável em ambos e C1 calibrado.
    Parâmetros desconhecidos levantam TypeError (sem **kwargs).
    """
    if data_source not in DATA_SOURCES:
        raise ValueError(f"data_source deve ser um de {DATA_SOURCES}: {data_source!r}")
    if not isinstance(n_campaigns_by_pair_type, dict):
        raise TypeError("n_campaigns_by_pair_type deve ser dict[(origem,destino,tipo)] -> int")
    n_by = {tuple(k): int(v) for k, v in n_campaigns_by_pair_type.items()}

    cm = champion_metrics if champion_metrics is not None else (b1_metrics or {})
    xm = challenger_metrics if challenger_metrics is not None else (c1_metrics or {})
    ci_b = bootstrap_ci_brier or ci_brier or ci or {}
    ci_l = bootstrap_ci_logloss or ci_logloss or ci or {}

    b_brier_c = cm.get("brier", cm.get("brier_score"))
    b_brier_x = xm.get("brier", xm.get("brier_score"))
    b_ll_c = cm.get("log_loss", cm.get("logloss"))
    b_ll_x = xm.get("log_loss", xm.get("logloss"))

    # calibração: sem informação => NÃO calibrado
    calibrated = False
    if challenger_calibrated is not None:
        calibrated = bool(challenger_calibrated)
    elif isinstance(reliability, dict):
        calibrated = bool(
            reliability.get("calibrated", reliability.get("is_calibrated", False))
        )
    elif isinstance(reliability, bool):
        calibrated = reliability

    # diff = champion - challenger; > 0 => challenger melhor
    lo_b, lo_l = ci_b.get("ci_low"), ci_l.get("ci_low")
    ci_b_favors = lo_b is not None and lo_b > 0
    ci_l_favors = lo_l is not None and lo_l > 0
    beats_brier = (
        b_brier_x is not None
        and b_brier_c is not None
        and float(b_brier_x) < float(b_brier_c)
    )
    beats_logloss = (
        b_ll_x is not None and b_ll_c is not None and float(b_ll_x) < float(b_ll_c)
    )

    reasons: list[str] = []
    if data_source != "real":
        reasons.append("dados sintéticos")
    if not n_by:
        reasons.append("dados insuficientes: nenhum (par,tipo) informado")
    for k in sorted(n_by):
        if n_by[k] < MIN_CAMPAIGNS_PER_PAIR_TYPE:
            reasons.append(
                f"dados insuficientes: {','.join(map(str, k))}={n_by[k]} "
                f"< {MIN_CAMPAIGNS_PER_PAIR_TYPE}"
            )
    data_gate_passed = not reasons
    if not beats_brier:
        reasons.append("Brier do challenger nao e menor")
    if not beats_logloss:
        reasons.append("log-loss do challenger nao e menor")
    if not ci_b_favors:
        reasons.append("IC de Brier inclui zero ou nao favorece challenger")
    if not ci_l_favors:
        reasons.append("IC de log-loss inclui zero ou nao favorece challenger")
    if not calibrated:
        reasons.append("challenger nao calibrado")

    promote = not reasons
    if promote:
        decision = "promote_challenger"
        note = (
            f"{challenger_name} vence {champion_name} em Brier e log-loss com IC "
            "excluindo zero, calibrado e com dados reais suficientes."
        )
    else:
        decision = "keep_champion"
        note = "; ".join(reasons) + f". {champion_name} permanece em producao."
    return {
        "decision": decision,
        "comparison": {
            "decision": decision,
            "promote": promote,
            "keep_champion": not promote,
            "delta_brier": (
                None
                if b_brier_c is None or b_brier_x is None
                else float(b_brier_c) - float(b_brier_x)
            ),
            "delta_log_loss": (
                None
                if b_ll_c is None or b_ll_x is None
                else float(b_ll_c) - float(b_ll_x)
            ),
            "ci_delta_brier": [ci_b.get("ci_low"), ci_b.get("ci_high")],
            "ci_delta_log_loss": [ci_l.get("ci_low"), ci_l.get("ci_high")],
        },
        "champion": champion_name,
        "challenger": challenger_name,
        "note": note,
        "promoted": promote,
        "calibrated": calibrated,
        "reasons": reasons,
        "data_source": data_source,
        "data_gate_passed": data_gate_passed,
        "n_campaigns_by_pair_type": n_by,
    }


champion_decision = decide_champion
challenger_decision = decide_champion
champion_challenger_decision = decide_champion
decide_promotion = decide_champion
should_promote = decide_champion


# ---------------------------------------------------------------------------
# Avaliação walk-forward C1 x B1 (alimenta o portão)
# ---------------------------------------------------------------------------


def _is_synthetic(rec: Any) -> bool:
    if _get(rec, "synthetic", "is_synthetic", default=False):
        return True
    return str(_get(rec, "data_source", default="")).lower() in {"synthetic", "sintetico"}


def _count_campaigns(records: Iterable[Any]) -> dict[tuple[str, str, str], int]:
    """Campanhas por (origem, destino, tipo), dedup por janela de ±3 dias."""
    by_key: dict[tuple, list[date]] = defaultdict(list)
    for r in records:
        s = _start(r)
        if s is not None:
            by_key[(_origin(r), _destination(r), _event_type(r))].append(s)
    out = {}
    for k, starts in by_key.items():
        starts.sort()
        n, last = 0, None
        for d in starts:
            if last is None or (d - last).days > 3:
                n += 1
            last = d
        out[k] = n
    return out


def _iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def evaluate_c1_vs_b1(
    records: Iterable[Any],
    *,
    horizons: Iterable[int] = (7, 15, 30),
    purge_days: int = 30,
    n_folds: int | None = None,
    train_months: int = 6,
    test_months: int = 3,
    step_months: int = 3,
    n_boot: int = 1000,
    seed: int = 42,
    data_source: str = "synthetic",
) -> dict[str, Any]:
    """Avalia B1 x C1 em walk-forward com purge; a saída alimenta decide_champion.

    Em cada dobra B1 e C1 são treinados só com first_seen_at <= corte (início
    do teste - purge_days) e preveem cada (par, tipo, t, h) do teste com
    as_of = t usando apenas registros com first_seen_at <= t. `data_source`
    é declarado por quem chama (default "synthetic": falha fechada).
    """
    from preditor.baseline import predict_proba as _b1_predict
    from preditor.walkforward import metrics as _metrics
    from preditor.walkforward import walk_forward_splits

    if data_source not in DATA_SOURCES:
        raise ValueError(f"data_source deve ser um de {DATA_SOURCES}: {data_source!r}")
    hs = tuple(int(h) for h in horizons)
    if not hs:
        raise ValueError("horizons vazio")
    if purge_days < max(hs):
        raise ValueError("purge_days deve ser >= max(horizons)")
    recs = list(records or [])
    splits = walk_forward_splits(
        recs,
        train_months=train_months,
        test_months=test_months,
        step_months=step_months,
        purge_days=purge_days,
        horizons=hs,
    )
    if n_folds is not None:
        splits = splits[-int(n_folds):]
    starts_all = [s for s in (_start(r) for r in recs) if s is not None]
    if not splits or not starts_all:
        raise ValueError("dados insuficientes para walk-forward")
    data_end = max(starts_all)
    keys = sorted(
        {(_origin(r), _destination(r), _event_type(r)) for r in recs},
        key=lambda k: tuple(str(x) for x in k),
    )

    cols: dict[str, list] = {
        k: [] for k in ("y", "p_b1", "p_c1", "t", "h", "origin", "destination",
                        "event_type", "blocks", "fold")
    }
    folds_meta: list[dict[str, Any]] = []
    train_union: dict[int, Any] = {}
    for fi, sp in enumerate(splits):
        cutoff = sp.test_start - timedelta(days=purge_days)
        cutoff_dt = _norm_dt(cutoff)
        train = [
            r
            for r in sp.train
            if (fs := _first_seen_dt(r)) is not None and fs <= cutoff_dt
        ]
        for r in train:
            train_union[id(r)] = r
        fs_max = max((_first_seen_dt(r) for r in train), default=None)
        test_days = sorted(
            {_start(r) for r in sp.test if _start(r) is not None}
        )
        t_lo, t_hi = sp.test_start, (test_days[-1] if test_days else sp.test_start)
        days = [t_lo + timedelta(days=i) for i in range((t_hi - t_lo).days + 1)]
        folds_meta.append(
            {
                "fold": fi,
                "cutoff": cutoff,
                "n_train": len(train),
                "train_max_first_seen": (
                    fs_max.date() if fs_max is not None else None
                ),
                "test_min_t": days[0],
                "test_max_t": days[-1],
            }
        )
        if not train:
            continue
        engine = C1(horizons=hs)
        engine.fit(train, as_of=cutoff, horizons=hs)
        grade = build_daily_grade(
            recs,
            horizons=hs,
            t_values=days,
            pairs={(k[0], k[1]) for k in keys},
            types={k[2] for k in keys},
            embargo_cutoff=data_end,
            include_features=False,
        )
        pool_cache: dict[date, list] = {}
        for row in grade:
            key = (row["origin"], row["destination"], row["event_type"])
            if key not in set(keys):
                continue
            t = row["t"]
            if t not in pool_cache:
                t_dt = _norm_dt(t)
                pool_cache[t] = [
                    r
                    for r in recs
                    if (fs := _first_seen_dt(r)) is not None and fs <= t_dt
                ]
            pool = pool_cache[t]
            h = row["h"]
            p_c1 = engine.predict_trained_at(*key, t, pool, [h])[h]
            p_b1 = _b1_predict(
                pool, *key, as_of=t, horizon=h, method="b1"
            )
            cols["y"].append(int(row["y"]))
            cols["p_b1"].append(float(p_b1))
            cols["p_c1"].append(float(p_c1))
            cols["t"].append(t)
            cols["h"].append(h)
            cols["origin"].append(key[0])
            cols["destination"].append(key[1])
            cols["event_type"].append(key[2])
            cols["blocks"].append(_iso_week(t))
            cols["fold"].append(fi)

    if not cols["y"]:
        raise ValueError("avaliacao sem linhas de teste")
    y, pb, pc, blocks = cols["y"], cols["p_b1"], cols["p_c1"], cols["blocks"]
    m_b1, m_c1 = _metrics(y, pb), _metrics(y, pc)
    ci_brier = block_bootstrap_ci(
        y, pb, pc, blocks=blocks, metric="brier", n_boot=n_boot, seed=seed
    )
    ci_logloss = block_bootstrap_ci(
        y, pb, pc, blocks=blocks, metric="log_loss", n_boot=n_boot, seed=seed
    )
    calibrated = bool(is_calibrated(y, pc))
    real_train = [r for r in train_union.values() if not _is_synthetic(r)]
    counted = _count_campaigns(real_train)
    n_by = {k: counted.get(k, 0) for k in keys}
    out: dict[str, Any] = {
        **cols,
        "metrics": {"b1": m_b1, "c1": m_c1},
        "ci_brier": ci_brier,
        "ci_logloss": ci_logloss,
        "calibrated": calibrated,
        "reliability": reliability_curve(y, pc),
        "n_campaigns_by_pair_type": n_by,
        "data_source": data_source,
        "folds": folds_meta,
        "purge_days": purge_days,
        "horizons": hs,
    }
    out["gate_inputs"] = {
        "champion_metrics": m_b1,
        "challenger_metrics": m_c1,
        "bootstrap_ci_brier": {k: ci_brier[k] for k in ("ci_low", "ci_high")},
        "bootstrap_ci_logloss": {k: ci_logloss[k] for k in ("ci_low", "ci_high")},
        "challenger_calibrated": calibrated,
        "n_campaigns_by_pair_type": n_by,
        "data_source": data_source,
    }
    return out


def record_decision_report(
    decision,
    path="docs/reports/t08b-champion-decision.md",
    *,
    data_source: str | None = None,
    n_campaigns_by_pair_type: dict | None = None,
):
    """Escreve o relatório. O banner 'SINTÉTICOS' é emitido sempre que os
    dados não são reais ou o portão de >= 25 campanhas por (par, tipo)
    reprova (inclusive quando a informação não foi fornecida)."""
    d = decision if isinstance(decision, dict) else {}
    dec = d.get("decision", "keep_champion")
    note = d.get("note", "")
    src = data_source if data_source is not None else d.get("data_source", "synthetic")
    n_by = (
        n_campaigns_by_pair_type
        if n_campaigns_by_pair_type is not None
        else d.get("n_campaigns_by_pair_type", {})
    ) or {}
    gate_ok = (
        src == "real"
        and bool(n_by)
        and min(int(v) for v in n_by.values()) >= MIN_CAMPAIGNS_PER_PAIR_TYPE
    )
    lines = ["# Decisão campeão × desafiante (T08b)", ""]
    if not gate_ok:
        lines += [
            "> **Atenção**: este resultado foi obtido com **dados SINTÉTICOS** (ou sem",
            "> campanhas reais suficientes) e só valida a mecânica do portão. A decisão",
            f"> real só vale com **≥ {MIN_CAMPAIGNS_PER_PAIR_TYPE} campanhas por (par, tipo)**.",
            "> Enquanto isso, B1 permanece em produção.",
            "",
        ]
    lines += [
        f"- Fonte de dados: **{src}**",
        f"- Decisão: **{dec}**",
        f"- Nota: {note}",
        "",
        "## Campanhas reais no treino por (par, tipo)",
        "",
        "| origem,destino,tipo | campanhas | mínimo |",
        "|---|---|---|",
    ]
    for k in sorted(n_by, key=lambda x: tuple(map(str, x))):
        lines.append(f"| {','.join(map(str, k))} | {n_by[k]} | {MIN_CAMPAIGNS_PER_PAIR_TYPE} |")
    if not n_by:
        lines.append("| (nenhum informado) | 0 | 25 |")
    lines += [
        "",
        "## Critérios aplicados",
        (
            "- C1 vira campeão apenas com dados reais, ≥ 25 campanhas por (par, tipo), "
            "vencendo B1 em Brier e log-loss com IC (bootstrap em blocos de semana ISO) "
            "excluindo zero e modelo calibrado."
        ),
        "- Caso contrário, B1 permanece em produção e o motivo é registrado aqui.",
        "",
    ]
    if d.get("reasons"):
        lines += ["## Motivos", *[f"- {r}" for r in d["reasons"]], ""]
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def run_champion_challenger(
    records: Iterable[Any],
    *,
    data_source: str = "synthetic",
    report_path: str | None = None,
    **eval_kwargs: Any,
) -> dict[str, Any]:
    """Avalia, decide e (opcionalmente) grava o relatório; nada digitado à mão."""
    ev = evaluate_c1_vs_b1(records, data_source=data_source, **eval_kwargs)
    decision = decide_champion(**ev["gate_inputs"])
    if report_path is not None:
        record_decision_report(decision, path=report_path)
    return {"evaluation": ev, "decision": decision}


# ---------------------------------------------------------------------------
# seeds calendar passthrough
# ---------------------------------------------------------------------------


def populate_calendar_events(*a, **k):
    return seed_calendar_events(*a, **k)


# Exports
__all__ = [
    "C1",
    "HORIZONS_DEFAULT",
    "SEED_EVENTS",
    "TZ",
    "C1Model",
    "ChallengerC1",
    "LightGBMGlobal",
    "LightGBMModel",
    "block_bootstrap",
    "block_bootstrap_ci",
    "bootstrap_block_ci",
    "bootstrap_ci",
    "build_daily_grade",
    "build_grade",
    "challenger_decision",
    "champion_decision",
    "daily_grade",
    "decide_champion",
    "evaluate_c1_vs_b1",
    "grade_diaria",
    "is_calibrated",
    "make_daily_grade",
    "populate_calendar_events",
    "record_decision_report",
    "reliability_curve",
    "run_champion_challenger",
    "seed_calendar_events",
]


def predict_proba(*args, **kwargs):
    method = kwargs.pop("method", kwargs.pop("model", kwargs.pop("mode", "c1")))
    name = str(method or "c1").lower()
    # if b0/b1 requested, delegate to baseline
    if name in {
        "b0",
        "b1",
        "base",
        "base_rate",
        "taxa",
        "taxa_base",
        "hazard",
        "b1_hazard",
    }:
        from preditor.baseline import predict_proba as _bp

        return _bp(*args, method=name, **kwargs)
    # C1 route
    origin = kwargs.pop("origin", None)
    destination = kwargs.pop("destination", None)
    event_type = kwargs.pop("event_type", None)
    if args:
        # support records positional first like baseline
        pass
    records = kwargs.pop("records", kwargs.pop("offers", kwargs.pop("data", None)))
    recs_input = None
    # args handling: if first arg is list of records
    if args and isinstance(args[0], (list, tuple, set)):
        recs_input = args[0]
        args = args[1:]
    if origin is None and len(args) > 0:
        origin = args[0]
    if destination is None and len(args) > 1:
        destination = args[1]
    if event_type is None and len(args) > 2:
        event_type = args[2]
    if recs_input is not None and records is not None:
        if isinstance(recs_input, (list, tuple, set)) and isinstance(
            records, (list, tuple, set)
        ):
            recs = list(recs_input) + list(records)
        else:
            recs = [recs_input, records]
    elif recs_input is not None:
        recs = (
            list(recs_input)
            if isinstance(recs_input, (list, tuple, set))
            else [recs_input]
        )
    elif records is not None:
        recs = list(records) if isinstance(records, (list, tuple, set)) else [records]
    else:
        recs = []
    as_of_raw = kwargs.pop("as_of", None)
    if as_of_raw is None:
        as_of_raw = kwargs.pop(
            "as_of_date",
            kwargs.pop(
                "cutoff",
                kwargs.pop(
                    "cutoff_date",
                    kwargs.pop("reference_date", kwargs.pop("current_date", None)),
                ),
            ),
        )
    if as_of_raw is None:
        raise ValueError("as_of e obrigatorio")
    _to_date(as_of_raw)
    horizon = kwargs.pop("horizon", kwargs.pop("h", None))
    horizons = kwargs.pop("horizons", None)
    if kwargs:
        raise TypeError(f"argumentos desconhecidos: {sorted(kwargs)}")
    m = C1()
    # fit will filter by as_of internally
    m.fit(recs, as_of=as_of_raw)
    if horizon is not None:
        return m.predict(
            origin, destination, event_type, as_of=as_of_raw, horizon=int(horizon)
        )
    if horizons is not None:
        return m.predict(
            origin,
            destination,
            event_type,
            as_of=as_of_raw,
            horizons=(horizons if isinstance(horizons, (list, tuple)) else [horizons]),
        )
    return m.predict(
        origin, destination, event_type, as_of=as_of_raw, horizons=HORIZONS_DEFAULT
    )
