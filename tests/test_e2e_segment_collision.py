"""E2E local: grupos segmentados do mesmo par nao podem sobrescrever a serie principal.

prediction/prediction_log nao tem coluna de segmento (chave: par, tipo, horizonte). Antes,
o grupo que chegasse primeiro ganhava o ON CONFLICT DO NOTHING e a probabilidade do par
saia da serie errada (ex.: 3 campanhas 'clube' no lugar das 23 do par principal).
"""
import datetime as _dt
import os
import random
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


@pytest.fixture(autouse=True)
def clean(engine):
    def wipe():
        with engine.begin() as c:
            # prediction_log e somente de insercao: cada teste usa um as_of unico
            for t in ("alert", "prediction", "offer", "model_run"):
                c.execute(text(f"DELETE FROM {t}"))

    wipe()
    yield
    wipe()


def _base():
    return D(2100, 1, 1) + _dt.timedelta(days=random.randrange(0, 60000))


def _offer(engine, start, segmented=False, label=""):
    fs = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) "
            "VALUES('livelo','smiles','transfer_bonus',:s,80,:g,:l,:f)"
        ), {"s": start, "g": segmented, "l": label, "f": fs})


def test_grupo_segmentado_nao_substitui_serie_principal(engine):
    from preditor.jobs.daily_predict import run_daily

    # 'clube' vem primeiro na ordem de insercao: antes ele vencia o conflito
    b = _base()
    for i in range(2):
        _offer(engine, b + _dt.timedelta(days=40 * i), True, "clube")
    for i in range(6):
        _offer(engine, b + _dt.timedelta(days=5 + 20 * i))
    res = run_daily(as_of=b + _dt.timedelta(days=200), engine=engine)
    with engine.connect() as c:
        rows = c.execute(text("SELECT explanation->>'n_campaigns', horizon_days FROM prediction")).fetchall()
        n_log = c.execute(text(
            "SELECT count(*) FROM prediction_log WHERE (logged_at AT TIME ZONE 'UTC')::date = :d"
        ), {"d": b + _dt.timedelta(days=200)}).scalar()
    assert len(rows) == 3 and {r[0] for r in rows} == {"6"}
    assert n_log == 3
    assert res["inserted_predictions"] == 3 and res["inserted_logs"] == 3


def test_par_so_segmentado_ainda_gera_predicao(engine):
    from preditor.jobs.daily_predict import run_daily

    b = _base()
    for i in range(2):
        _offer(engine, b + _dt.timedelta(days=40 * i), True, "clube")
    res = run_daily(as_of=b + _dt.timedelta(days=200), engine=engine)
    assert res["inserted_predictions"] == 3


def test_reexecucao_nao_conta_conflitos_como_inseridos(engine):
    from preditor.jobs.daily_predict import run_daily

    b = _base()
    for i in range(4):
        _offer(engine, b + _dt.timedelta(days=20 * i))
    run_daily(as_of=b + _dt.timedelta(days=200), engine=engine)
    again = run_daily(as_of=b + _dt.timedelta(days=200), engine=engine)
    assert again["inserted_predictions"] == 0 and again["inserted_logs"] == 0
