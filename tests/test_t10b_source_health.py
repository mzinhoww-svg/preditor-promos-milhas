"""T10b (5): /v1/source-health lido da tabela source_health (alimentada pelo listener, PR #49)."""
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
H = {"X-API-Key": "test-key"}


@pytest.fixture(scope="module")
def engine():
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=dict(os.environ))
    from preditor.api.db import get_engine

    return get_engine()


@pytest.fixture(autouse=True)
def clean(engine):
    with engine.begin() as c:
        c.execute(text("DELETE FROM source_health"))
    yield
    with engine.begin() as c:
        c.execute(text("DELETE FROM source_health"))


def _row(engine, source, when, items, rate=0.9, alert=False, robots=None):
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO source_health(source, checked_at, items_new, extraction_rate, alert, robots_hash) "
            "VALUES (:s,:t,:i,:e,:a,:r)"
        ), {"s": source, "t": when, "i": items, "e": rate, "a": alert, "r": robots})


def _get(engine):
    from fastapi.testclient import TestClient

    from preditor.api import create_app

    os.environ["PREDITOR_API_KEY"] = "test-key"
    with TestClient(create_app()) as cl:
        return cl.get("/v1/source-health", headers=H).json()["sources"]


def test_agrega_24h_e_7d_por_fonte(engine):
    now = datetime.now(UTC)
    _row(engine, "livelo", now - _dt.timedelta(hours=2), 3)
    _row(engine, "livelo", now - _dt.timedelta(days=3), 4)
    _row(engine, "livelo", now - _dt.timedelta(days=20), 50)  # fora de 7d
    s = {x["source"]: x for x in _get(engine)}
    assert s["livelo"]["items_new_24h"] == 3
    assert s["livelo"]["items_new_7d"] == 7


def test_status_degraded_e_robots_changed(engine):
    now = datetime.now(UTC)
    _row(engine, "esfera", now - _dt.timedelta(days=1), 2, robots="aaa")
    _row(engine, "esfera", now - _dt.timedelta(hours=1), 0, alert=True, robots="bbb")
    s = {x["source"]: x for x in _get(engine)}
    assert s["esfera"]["status"] == "degraded"
    assert s["esfera"]["robots_changed"] is True
    assert s["esfera"]["robots_hash"] == "bbb"
    assert s["esfera"]["last_success_at"] is not None
