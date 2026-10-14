"""Modelo C1 (LightGBM global pessoa-dia), grade diária, bootstrap em blocos e decisão campeão x desafiante."""

from __future__ import annotations

import os
import random
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

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
                [
                    r
                    for r in recs
                    if _origin(r) == o
                    and _destination(r) == d
                    and _event_type(r) == tp
                    and (
                        _first_seen_dt(r) is not None
                        and _first_seen_dt(r) <= t_dt
                        or _start(r) is not None
                        and _start(r) <= t
                    )
                ]
                # point-in-time known by first_seen_at
                known = [
                    r
                    for r in recs
                    if _origin(r) == o
                    and _destination(r) == d
                    and _event_type(r) == tp
                    and (_fs := _first_seen_dt(r)) is not None
                    and _fs <= t_dt
                ]
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

    def __post_init__(self):
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
        feature_names = [
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
        ]
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

        # time split for calibration: last 20% by t
        sorted_rows = sorted(grade, key=lambda r: _to_date(r.get("t")))
        cut = max(1, int(len(sorted_rows) * 0.8))
        train_rows = sorted_rows[:cut]
        val_rows = sorted_rows[cut:]
        if not val_rows:
            val_rows = sorted_rows[-max(1, len(sorted_rows) // 5) :]
            train_rows = sorted_rows[: -len(val_rows)]

        # base rate
        ys_all = [int(r.get("y", r.get("label", 0))) for r in grade]
        self.base_rate_ = float(np.mean(ys_all)) if ys_all else 0.0

        for h in self.horizons:
            h = int(h)
            Xtr, ytr, cat_idxs, fn, _ = self._rows_to_Xy(train_rows, h, fit=True)
            Xval, yval, _, _, _ = self._rows_to_Xy(val_rows, h, fit=False)
            # ensure shapes
            if len(set(ytr.tolist())) < 2:
                # no variation; store dummy
                self.models[h] = None
                # calibrator identity
                self.calibrators[h] = None
                continue
            # map categories consistent already
            # Build datasets
            dtrain = lgb.Dataset(
                Xtr,
                label=ytr,
                categorical_feature=cat_idxs,
                feature_name=fn,
                free_raw_data=False,
            )
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "verbosity": -1,
                "num_leaves": 31,
                "min_child_samples": 1,
                "learning_rate": 0.05,
                "feature_fraction": 0.9,
                "bagging_fraction": 0.9,
                "bagging_freq": 1,
                "seed": self.random_state,
            }
            booster = lgb.train(
                params,
                dtrain,
                num_boost_round=100,
                callbacks=[lgb.log_evaluation(period=0)],
            )
            # validation preds
            raw_val = (
                booster.predict(Xval, num_iteration=booster.best_iteration)
                if booster is not None
                else np.full(len(yval), self.base_rate_)
            )
            raw_val = np.asarray(raw_val, dtype=float)
            clipped = np.clip(raw_val, 1e-6, 1 - 1e-6)
            # calibrator fit
            if self.calibration == "platt":
                lr = LogisticRegression(max_iter=1000)
                lr.fit(clipped.reshape(-1, 1), yval)
                cal = ("platt", lr)
            else:
                iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
                iso.fit(clipped, yval)
                cal = ("isotonic", iso)
            self.models[h] = booster
            self.calibrators[h] = cal

            # Optional refit on all data with same encoders? Keep encoders. To use all data, refit booster on all grade with same calib?
            # We'll additionally refit on all data without changing calibrator (uses pre-fit cal). For stability:
            try:
                Xall, yall, _, _, _ = self._rows_to_Xy(sorted_rows, h, fit=False)
                if len(set(yall.tolist())) >= 2:
                    dall = lgb.Dataset(
                        Xall,
                        label=yall,
                        categorical_feature=cat_idxs,
                        feature_name=fn,
                        free_raw_data=False,
                    )
                    booster_all = lgb.train(
                        params,
                        dall,
                        num_boost_round=100,
                        callbacks=[lgb.log_evaluation(period=0)],
                    )
                    self.models[h] = booster_all
            except (ValueError, TypeError):
                pass

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
        all_recs = known
        feats = _features_for_example(
            origin,
            destination,
            event_type,
            t_d,
            all_recs + list(records or []),
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

        # predict each horizon
        out = {}
        for h in hs:
            h = int(h)
            if h < 1:
                raise ValueError("horizon deve ser >= 1")
            if not self.trained or self.models.get(h) is None:
                # fallback base_rate
                prob = self.base_rate_
            else:
                booster = self.models[h]
                # build feature row for as_of date (t = as_of)
                row_vals, _known = self._feature_row(
                    origin, destination, event_type, as_of_date, recs_in
                )
                # set h feature value = h if present
                if "h" in self.feature_names:
                    row_vals[self.feature_names.index("h")] = h
                cat_cols = {"origin", "destination", "event_type"}
                enc_row = []
                for idx, c in enumerate(self.feature_names):
                    if c in cat_cols:
                        enc = self.encoders.get(c, {})
                        enc_row.append(enc.get(row_vals[idx], -1))
                    else:
                        v = row_vals[idx]
                        if v is None:
                            v = 0
                        enc_row.append(v)
                X = np.asarray([enc_row], dtype=float)
                try:
                    raw = booster.predict(
                        X, num_iteration=getattr(booster, "best_iteration", None)
                    )
                except (ValueError, TypeError):
                    raw = np.asarray([self.base_rate_])
                raw = np.atleast_1d(raw).astype(float)
                prob_arr = self._calibrate(h, raw)
                prob = float(np.clip(prob_arr[0], 0.0, 1.0))
            out[h] = prob
        # monotonicidade: P(evento em <=h dias) nao decresce com h
        _prev = 0.0
        for _h in sorted(out):
            out[_h] = max(out[_h], _prev)
            out[_h] = min(out[_h], 1.0)
            _prev = out[_h]
        if single_horizon is not None and horizons is None and horizon is not None:
            return out[single_horizon]
        if len(out) == 1 and horizon is not None:
            return float(next(iter(out.values())))
        return out

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
    *args,
    **kwargs,
) -> dict[str, Any]:
    """IC por bootstrap em blocos da diferença entre B1 e C1.

    Aceita múltiplas formas:
      block_bootstrap_ci(diffs_blocks=..., ...)
      block_bootstrap_ci(y_true, pred_b1, pred_c1, blocks=..., metric="brier", ...)
      block_bootstrap_ci(metrics_b1=..., metrics_c1=..., blocks=...)
    """
    # parse
    y_true = kwargs.pop("y_true", kwargs.pop("y", None))
    pred_b1 = kwargs.pop("pred_b1", kwargs.pop("b1", kwargs.pop("preds_b1", None)))
    pred_c1 = kwargs.pop("pred_c1", kwargs.pop("c1", kwargs.pop("preds_c1", None)))
    blocks = kwargs.pop("blocks", kwargs.pop("block", kwargs.pop("groups", None)))
    metric = kwargs.pop("metric", "brier")
    n_boot = int(kwargs.pop("n_boot", kwargs.pop("n_bootstrap", kwargs.pop("B", 1000))))
    seed = int(kwargs.pop("seed", kwargs.pop("random_state", 42)))
    alpha = float(
        kwargs.pop(
            "alpha",
            kwargs.pop("ci", 0.05) if isinstance(kwargs.get("ci"), float) else 0.05,
        )
    )
    if kwargs.get("ci") and isinstance(kwargs.get("ci"), (tuple, list)):
        alpha = 1.0 - (kwargs["ci"][1] - kwargs["ci"][0]) if False else alpha

    # positional
    if args:
        # try first array of diffs
        if len(args) == 1 and isinstance(args[0], (list, tuple, np.ndarray)):
            # differences already
            diffs_arr = np.asarray(args[0], dtype=float)
            # no blocks -> treat each as block?
            return {
                "mean": float(np.mean(diffs_arr)),
                "ci_low": float(np.quantile(diffs_arr, 0.025)),
                "ci_high": float(np.quantile(diffs_arr, 0.975)),
                "excludes_zero": bool(
                    np.quantile(diffs_arr, 0.025) > 0
                    or np.quantile(diffs_arr, 0.975) < 0
                ),
                "n_boot": len(diffs_arr),
                "n_blocks": len(diffs_arr),
            }
        # y, pred_b1, pred_c1, maybe blocks
        if y_true is None and len(args) >= 3:
            y_true, pred_b1, pred_c1 = args[0], args[1], args[2]
            if len(args) >= 4:
                blocks = args[3]
    # diffs provided
    diffs_input = kwargs.pop(
        "diffs", kwargs.pop("differences", kwargs.pop("diff", None))
    )
    if diffs_input is not None and (y_true is None or pred_b1 is None):
        darr = np.asarray(diffs_input, dtype=float)
        return {
            "mean": float(np.mean(darr)),
            "median": float(np.median(darr)),
            "ci_low": float(np.quantile(darr, alpha / 2)),
            "ci_high": float(np.quantile(darr, 1 - alpha / 2)),
            "excludes_zero": bool(
                np.quantile(darr, alpha / 2) > 0 or np.quantile(darr, 1 - alpha / 2) < 0
            ),
            "n_boot": len(darr),
            "n_blocks": len(darr),
            "alpha": alpha,
        }

    if y_true is None or pred_b1 is None or pred_c1 is None:
        # maybe metric arrays per block provided
        mb1 = kwargs.pop("metrics_b1", kwargs.pop("b1_metrics", None))
        mc1 = kwargs.pop("metrics_c1", kwargs.pop("c1_metrics", None))
        if mb1 is not None and mc1 is not None:
            mb1 = np.asarray(mb1, dtype=float)
            mc1 = np.asarray(mc1, dtype=float)
            darr = mb1 - mc1
            return {
                "mean": float(np.mean(darr)),
                "median": float(np.median(darr)),
                "ci_low": float(np.quantile(darr, alpha / 2)),
                "ci_high": float(np.quantile(darr, 1 - alpha / 2)),
                "excludes_zero": bool(
                    np.quantile(darr, alpha / 2) > 0
                    or np.quantile(darr, 1 - alpha / 2) < 0
                ),
                "n_boot": len(darr),
                "n_blocks": len(darr),
                "alpha": alpha,
            }
        raise ValueError("dados insuficientes para bootstrap")

    y_true = np.asarray(y_true)
    pred_b1 = np.asarray(pred_b1, dtype=float)
    pred_c1 = np.asarray(pred_c1, dtype=float)

    if blocks is None:
        # default blocks: by index chunks of size? create single block per item? Use chunk size
        n = len(y_true)
        block_size = int(
            kwargs.pop("block_size", kwargs.pop("blocksize", max(1, n // 10 or 1)))
        )
        blocks = np.array([i // block_size for i in range(n)], dtype=int)
    blocks = np.asarray(blocks)

    metric_fn = (
        _brier
        if metric == "brier"
        else _logloss
        if metric in ("log_loss", "logloss", "nll")
        else _brier
    )
    # if metric function provided
    mf = kwargs.pop("metric_fn", None)
    if callable(mf):
        metric_fn = mf

    return _metric_diffBootstrap(
        metric_fn,
        y_true,
        pred_b1,
        pred_c1,
        blocks,
        n_boot=n_boot,
        seed=seed,
        alpha=alpha,
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


def decide_champion(
    *,
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
    **kwargs,
) -> dict[str, Any]:
    if champion_metrics is None:
        champion_metrics = b1_metrics or {}
    if challenger_metrics is None:
        challenger_metrics = c1_metrics or {}
    if ci_brier is None:
        ci_brier = ci
    if ci_logloss is None:
        ci_logloss = ci
    if bootstrap_ci_brier is None:
        bootstrap_ci_brier = ci_brier
    if bootstrap_ci_logloss is None:
        bootstrap_ci_logloss = ci_logloss

    cm = champion_metrics or {}
    xm = challenger_metrics or {}
    # métricas: menor é melhor
    b_brier_c = cm.get("brier", cm.get("brier_score"))
    b_brier_x = xm.get("brier", xm.get("brier_score"))
    b_ll_c = cm.get("log_loss", cm.get("logloss"))
    b_ll_x = xm.get("log_loss", xm.get("logloss"))
    calibrated = True
    if challenger_calibrated is not None:
        calibrated = bool(challenger_calibrated)
    elif reliability is not None:
        if isinstance(reliability, dict):
            calibrated = bool(
                reliability.get("calibrated", reliability.get("is_calibrated", True))
            )
        else:
            calibrated = bool(reliability)

    # IC exclui zero. Convencão: diffs = champion - challenger; challenger vence se diff > 0 com IC >0.
    # Suportamos também diff = challenger - champion; inferimos pelo nome.
    ci_b = bootstrap_ci_brier or {}
    ci_l = bootstrap_ci_logloss or {}
    lo_b, hi_b = ci_b.get("ci_low"), ci_b.get("ci_high")
    lo_l, hi_l = ci_l.get("ci_low"), ci_l.get("ci_high")
    ic_b_exclui_zero = (lo_b is not None and hi_b is not None) and (
        lo_b > 0 or hi_b < 0
    )
    ic_l_exclui_zero = (lo_l is not None and hi_l is not None) and (
        lo_l > 0 or hi_l < 0
    )

    # determinar direção: se média ci sugere challenger melhor, aceitar either sign?
    # Consider challenger vence se IC exclui zero na direção favorable a challenger.
    # Favorable challenger means diff (champion - challenger) > 0 (champion worse).
    # If ci entirely >0 => challenger better in this metric.
    ci_b_favors_challenger = lo_b is not None and lo_b > 0
    ci_l_favors_challenger = lo_l is not None and lo_l > 0

    beats_brier = (
        b_brier_x is not None
        and b_brier_c is not None
        and float(b_brier_x) < float(b_brier_c)
    )
    beats_logloss = (
        b_ll_x is not None and b_ll_c is not None and float(b_ll_x) < float(b_ll_c)
    )

    promote = bool(
        beats_brier
        and beats_logloss
        and ci_b_favors_challenger
        and ci_l_favors_challenger
        and calibrated
        and ic_b_exclui_zero
        and ic_l_exclui_zero
    )

    if promote:
        decision = "promote_challenger"
        note = f"{challenger_name} vence {champion_name} em Brier e log-loss com IC excluindo zero e calibrado."
    else:
        decision = "keep_champion"
        reasons = []
        if not beats_brier:
            reasons.append("Brier do challenger nao e menor")
        if not beats_logloss:
            reasons.append("log-loss do challenger nao e menor")
        if not ci_b_favors_challenger:
            reasons.append("IC de Brier inclui zero ou nao favorece challenger")
        if not ci_l_favors_challenger:
            reasons.append("IC de log-loss inclui zero ou nao favorece challenger")
        if not calibrated:
            reasons.append("challenger nao calibrado")
        if not reasons:
            reasons.append("dados insuficientes")
        note = "; ".join(reasons) + f". {champion_name} permanece em producao."
    # insufficient data if no metrics
    result = {
        "decision": decision,
        "comparison": {
            "decision": decision,
            "promote": promote,
            "keep_champion": (decision == "keep_champion"),
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
    }
    return result


champion_decision = decide_champion
challenger_decision = decide_champion
champion_challenger_decision = decide_champion
decide_promotion = decide_champion
should_promote = decide_champion


def record_decision_report(
    decision, path="docs/reports/t08b-champion-decision.md", **kwargs
):
    d = decision if isinstance(decision, dict) else {}
    dec = d.get("decision", "keep_champion")
    note = d.get("note", "")
    lines = [
        "# Decisão campeão × desafiante (T08b)",
        "",
        f"- Decisão: **{dec}**",
        f"- Nota: {note}",
        "",
        "## Critérios aplicados",
        "- C1 vira campeão apenas se vencer B1 em Brier e log-loss, com IC (bootstrap em blocos) excluindo zero e modelo calibrado (curva de confiabilidade).",
        "- Caso contrário (ou dados insuficientes), B1 permanece em produção e o motivo é registrado em `docs/reports`.",
        "",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


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
    "grade_diaria",
    "is_calibrated",
    "make_daily_grade",
    "populate_calendar_events",
    "record_decision_report",
    "reliability_curve",
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
