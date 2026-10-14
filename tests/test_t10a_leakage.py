"""Ataques de vazamento temporal do T10a (P1, J1b, J1c)."""
import datetime as _dt
import os
import subprocess
import sys
from datetime import datetime

import pytest
from sqlalchemy import text

URL_DB = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")

UTC = _dt.UTC
D = _dt.date


@pytest.fixture(scope="module")
def engine():
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=dict(os.environ))
    from preditor.api.db import get_engine

    return get_engine()


def _wipe(engine):
    with engine.begin() as c:
        c.execute(text("DELETE FROM prediction"))
        c.execute(text("DELETE FROM offer"))
        c.execute(text("DELETE FROM model_run"))


@pytest.fixture(autouse=True)
def clean(engine):
    _wipe(engine)
    yield
    _wipe(engine)


def _offer(engine, o, d, start, first_seen=None, bonus=80):
    fs = first_seen or datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) "
                "VALUES(:o,:d,'transfer_bonus',:s,:b,false,'',:f)"
            ),
            {"o": o, "d": d, "s": start, "b": bonus, "f": fs},
        )


def _pred_pairs(engine):
    with engine.connect() as c:
        return {(r[0], r[1]) for r in c.execute(text("SELECT origin,destination FROM prediction"))}


def test_j1b_par_visto_so_depois_de_as_of_nao_e_previsto(engine):
    from preditor.jobs.daily_predict import run_daily

    for i in range(3):
        _offer(engine, "livelo", "smiles", D(2026, 1, 1) + _dt.timedelta(days=30 * i))
    _offer(engine, "esfera", "latam", D(2026, 8, 1))
    run_daily(as_of="2026-06-01", engine=engine)
    assert _pred_pairs(engine) == {("livelo", "smiles")}


def test_j1c_metodo_usa_contagem_point_in_time(engine):
    from preditor.jobs.daily_predict import run_daily

    for i in range(3):
        _offer(engine, "livelo", "smiles", D(2025, 1, 1) + _dt.timedelta(days=30 * i))
    for i in range(27):
        _offer(engine, "livelo", "smiles", D(2026, 7, 1) + _dt.timedelta(days=10 * i))
    run_daily(as_of="2026-06-01", engine=engine)
    with engine.connect() as c:
        versions = {r[0] for r in c.execute(text("SELECT DISTINCT model_version FROM prediction_log WHERE logged_at = '2026-06-01 00:00+00'"))}
    assert versions == {"B0"}


def test_p1_api_serve_predicao_mais_recente(engine, monkeypatch):
    os.environ["PREDITOR_API_KEY"] = "test-key"
    from fastapi.testclient import TestClient

    from preditor.api import create_app

    with engine.begin() as c:
        mr = c.execute(text(
            "INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, hyperparams, metrics, code_hash, is_champion) "
            "VALUES ('B1', now(), 'd','1','{}'::jsonb,'{}'::jsonb,'h',TRUE) RETURNING id"
        )).scalar()
        for day, p in ((1, 0.11), (2, 0.99)):
            for h in (7, 15, 30):
                c.execute(text(
                    "INSERT INTO prediction (made_at, model_run_id, origin, destination, event_type, horizon_days, probability) "
                    "VALUES (:m, :mr, 'livelo','smiles','transfer_bonus', :h, :p)"
                ), {"m": datetime(2026, 10, day, tzinfo=UTC), "mr": mr, "h": h, "p": p})
    with TestClient(create_app()) as cl:
        r = cl.get("/v1/predictions", headers={"X-API-Key": "test-key"})
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["windows"]["7"]["probability"] == 0.99
    assert items[0]["windows"]["30"]["probability"] == 0.99
