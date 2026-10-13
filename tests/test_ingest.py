import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from preditor.ingest import content_hash, store_raw_message

URL_DB = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")


@pytest.fixture(scope="module")
def engine():
    import subprocess
    import sys
    env = dict(os.environ)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
    eng = create_engine(URL_DB)
    yield eng


def test_ingest_idempotent_and_stores_url_collected_at(engine):
    # limpa
    with engine.begin() as c:
        c.execute(text("DELETE FROM raw_message WHERE source='t05a-test'"))
    collected = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    first = store_raw_message(engine, "t05a-test", "https://x", "conteudo bruto", collected_at=collected)
    second = store_raw_message(engine, "t05a-test", "https://x", "conteudo bruto", collected_at=collected)
    assert first.id == second.id
    assert first.url == "https://x"
    assert first.content_hash == content_hash("conteudo bruto")
    assert first.collected_at is not None

    # confirma apenas uma linha
    with engine.connect() as c:
        n = c.execute(text("SELECT count(*) FROM raw_message WHERE source='t05a-test'")).scalar_one()
    assert n == 1


def test_ingest_different_content_creates_new_row(engine):
    with engine.begin() as c:
        c.execute(text("DELETE FROM raw_message WHERE source='t05a-test2'"))
    a = store_raw_message(engine, source="t05a-test2", url="https://y", content="a")
    b = store_raw_message(engine, source="t05a-test2", url="https://y", content="b")
    assert a.id != b.id
