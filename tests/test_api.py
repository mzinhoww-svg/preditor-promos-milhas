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
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
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
    r = client.get("/v1/source-health", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["sources"] == []


def test_accuracy_empty(client):
    r = client.get("/v1/prediction-log/accuracy", headers=HEADERS)
    assert r.status_code == 200
