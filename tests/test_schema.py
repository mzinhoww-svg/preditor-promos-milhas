import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="DATABASE_URL ausente")


def alembic(*args):
    subprocess.run([sys.executable, "-m", "alembic", *args], check=True, env=os.environ)


@pytest.fixture(scope="module")
def engine():
    alembic("downgrade", "base")
    alembic("upgrade", "head")
    alembic("upgrade", "head")  # idempotente
    yield create_engine(URL)
    alembic("downgrade", "base")


def test_prediction_log_is_append_only(engine):
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO prediction_log(model_version,origin,destination,event_type,"
            "horizon_days,probability) VALUES ('b1','livelo','smiles','transfer_bonus',30,0.4)"))
    for stmt in ("UPDATE prediction_log SET probability=0.9",
                 "DELETE FROM prediction_log", "TRUNCATE prediction_log"):
        with pytest.raises(DBAPIError), engine.begin() as c:
            c.execute(text(stmt))


def test_offer_unique_key_blocks_duplicate(engine):
    ins = text("INSERT INTO offer(origin,destination,event_type,start_at,first_seen_at,"
               "segmented,segment_label) VALUES ('livelo','smiles','transfer_bonus',"
               "'2026-03-10',now(),false,'')")
    with engine.begin() as c:
        c.execute(ins)
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(ins)


def test_sql_ledger_roundtrip(engine):
    from preditor.budget import Budget, SqlLedger

    b = Budget(SqlLedger(engine), caps={"openrouter": 1.0})
    b.charge("openrouter", 0.4)
    assert b.spent("openrouter") == pytest.approx(0.4)
