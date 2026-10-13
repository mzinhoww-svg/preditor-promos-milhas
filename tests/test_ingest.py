import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from preditor.ingest import (
    EmptyContentError,
    EmptySourceError,
    InvalidCollectedAtError,
    InvalidURLError,
    InvalidUTF8Error,
    NullByteError,
    content_hash,
    store_raw_message,
)

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


def _cleanup(engine, source):
    with engine.begin() as c:
        c.execute(text("DELETE FROM raw_message WHERE source=:s"), {"s": source})


def test_ingest_idempotent_and_stores_url_collected_at(engine):
    _cleanup(engine, "t05a-test")
    collected = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    first = store_raw_message(engine, "t05a-test", "https://x", "conteudo bruto", collected_at=collected)
    second = store_raw_message(engine, "t05a-test", "https://x", "conteudo bruto", collected_at=collected)
    assert first.id == second.id
    assert first.url == "https://x"
    assert first.content_hash == content_hash("conteudo bruto")
    assert first.collected_at is not None
    with engine.connect() as c:
        n = c.execute(text("SELECT count(*) FROM raw_message WHERE source='t05a-test'")).scalar_one()
    assert n == 1


def test_ingest_different_content_creates_new_row(engine):
    _cleanup(engine, "t05a-test2")
    a = store_raw_message(engine, source="t05a-test2", url="https://y", content="a")
    b = store_raw_message(engine, source="t05a-test2", url="https://y", content="b")
    assert a.id != b.id


def test_rejects_empty_content(engine):
    _cleanup(engine, "t-empty")
    with pytest.raises(EmptyContentError):
        store_raw_message(engine, "t-empty", "https://x", "   ")
    with pytest.raises(EmptyContentError):
        store_raw_message(engine, "t-empty", "https://x", "")


def test_rejects_invalid_url(engine):
    _cleanup(engine, "t-url")
    for bad in ("", "nao-eh-url", "javascript:alert(1)", "ftp://x.com", "http://"):
        with pytest.raises(InvalidURLError):
            store_raw_message(engine, "t-url", bad, "conteudo")


def test_rejects_empty_source(engine):
    _cleanup(engine, "t-src")
    with pytest.raises(EmptySourceError):
        store_raw_message(engine, "", "https://x", "conteudo")


def test_collected_at_invalid_raises(engine):
    _cleanup(engine, "t-ca")
    with pytest.raises(InvalidCollectedAtError):
        store_raw_message(engine, "t-ca", "https://x", "conteudo", collected_at="lixo")
    # futuro aceito
    future = store_raw_message(engine, "t-ca", "https://x", "futuro", collected_at="2999-01-01T00:00:00+00:00")
    assert future.collected_at is not None


def test_rejects_null_byte(engine):
    _cleanup(engine, "t-null")
    with pytest.raises(NullByteError):
        store_raw_message(engine, "t-null", "https://x", "a\x00b")


def test_rejects_non_utf8_bytes(engine):
    _cleanup(engine, "t-bytes")
    with pytest.raises(InvalidUTF8Error):
        store_raw_message(engine, "t-bytes", "https://x", b"\xff\xfe")


def test_valid_bytes_accepted(engine):
    _cleanup(engine, "t-bytes-ok")
    raw = "café"
    r = store_raw_message(engine, "t-bytes-ok", "https://x", raw.encode("utf-8"))
    assert r.content == raw
