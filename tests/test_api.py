import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

URL_DB = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")


@pytest.fixture(scope="module")
def client():
    env = dict(os.environ)
    env["PREDITOR_API_KEY"] = "test-key"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env
    )
    os.environ["PREDITOR_API_KEY"] = "test-key"
    from preditor.api import create_app

    with TestClient(create_app()) as c:
        yield c


HEADERS = {"X-API-Key": "test-key"}


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200


def test_requires_key(client):
    r = client.get("/v1/predictions")
    assert r.status_code == 401


def test_invalid_key(client):
    r = client.get("/v1/predictions", headers={"X-API-Key": "wrong"})
    assert r.status_code == 403


def test_predictions_empty(client):
    r = client.get("/v1/predictions", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert "generated_at" in data
    assert "model" in data


def test_model_metrics_empty(client):
    r = client.get("/v1/model/metrics", headers=HEADERS)
    assert r.status_code == 200


def test_source_health_empty(client):
    from sqlalchemy import text as _t

    from preditor.api.db import get_engine as _ge

    with _ge().begin() as c:
        c.execute(_t("DELETE FROM source_health"))
    r = client.get("/v1/source-health", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["sources"] == []


def test_accuracy_empty(client):
    r = client.get("/v1/prediction-log/accuracy", headers=HEADERS)
    assert r.status_code == 200


import datetime as _dt
from datetime import datetime

from sqlalchemy import text

from preditor.api.db import get_engine
from preditor.api.queries import fetch_prediction_accuracy
from preditor.jobs.daily_predict import run_daily

UTC = _dt.UTC


def _insert_offer(
    engine,
    origin,
    destination,
    start,
    bonus=80,
    segmented=False,
    label="",
    first_seen=None,
):
    fs = first_seen or datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) "
                "VALUES(:o,:d,'transfer_bonus',:s,:b,:g,:l,:f)"
            ),
            {
                "o": origin,
                "d": destination,
                "s": start,
                "b": bonus,
                "g": segmented,
                "l": label,
                "f": fs,
            },
        )


def test_job_daily_runs_with_offers():
    engine = get_engine()
    with engine.begin() as c:
        c.execute(text("DELETE FROM prediction"))
        c.execute(text("DELETE FROM offer_evidence"))
        c.execute(text("DELETE FROM offer"))

    base = _dt.date(2025, 1, 1)
    for i in range(30):
        _insert_offer(engine, "Livelo", "Smiles", base + _dt.timedelta(days=i * 10), 80)
    future = _dt.date(2027, 6, 10)
    _insert_offer(
        engine,
        "Livelo",
        "Smiles",
        future,
        999,
        first_seen=datetime.combine(future, datetime.min.time(), tzinfo=UTC),
    )

    result = run_daily(as_of="2029-05-01", engine=engine)
    assert result["pairs"] == 1
    assert result["inserted_predictions"] == 3
    assert result["inserted_logs"] == 3

    again = run_daily(as_of="2029-05-01", engine=engine)
    assert again["inserted_logs"] == 0

    with engine.connect() as c:
        n = c.execute(
            text(
                "SELECT count(*) FROM prediction WHERE origin='Livelo' AND destination='Smiles'"
            )
        ).scalar()
    assert n == 3


def test_prediction_accuracy_with_data_no_500():
    engine = get_engine()
    with engine.begin() as c:
        c.execute(text("DELETE FROM prediction"))
        c.execute(text("DELETE FROM offer_evidence"))
        c.execute(text("DELETE FROM offer"))

    base = _dt.date(2025, 1, 1)
    for i in range(30):
        _insert_offer(engine, "Livelo", "Smiles", base + _dt.timedelta(days=i * 10), 80)
    future = _dt.date(2026, 6, 10)
    _insert_offer(
        engine,
        "Livelo",
        "Smiles",
        future,
        999,
        first_seen=datetime.combine(future, datetime.min.time(), tzinfo=UTC),
    )

    run_daily(as_of="2026-06-05", engine=engine)
    acc = fetch_prediction_accuracy(date_from="2026-06-05", date_to="2026-06-05")
    assert "by_horizon" in acc
    assert set(acc["by_horizon"].keys()) == {"7", "15", "30"}
    for v in acc["by_horizon"].values():
        assert v["n"] >= 0
