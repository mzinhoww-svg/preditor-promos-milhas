"""T10b ciclo 1: STOP e kill switch real (CLI do backfill, listener) e dentro dos laços longos."""
import os
import subprocess
import sys

import pytest

from preditor import backfill as BF
from preditor.jobs import feed_listener as FL
from preditor.stop import StopRequested


class _Boom:
    def __getattr__(self, name):
        raise AssertionError(f"engine tocado ({name}) com STOP presente")


@pytest.fixture
def stop_file(tmp_path, monkeypatch):
    f = tmp_path / "STOP"
    monkeypatch.setenv("PREDITOR_STOP_FILE", str(f))
    monkeypatch.delenv("PREDITOR_STOP", raising=False)
    return f


# ---- backfill ---------------------------------------------------------------
def test_stop_e_excecao_fora_de_runtimeerror():
    # os laços usam `except (OSError, ValueError, RuntimeError, TypeError)`: STOP nao pode ser engolido
    assert not issubclass(StopRequested, (RuntimeError, OSError, ValueError, TypeError))


@pytest.mark.parametrize("argv", [["--reprocess"], ["--rss-archive", "http://x/feed"], ["--rss-titles", "http://x/feed"], []])
def test_backfill_main_aborta_com_stop(stop_file, monkeypatch, argv):
    stop_file.write_text("")
    monkeypatch.setattr(BF, "_engine", lambda args: _Boom())
    assert BF.main(argv) == 3


def test_run_backfill_aborta_com_stop(stop_file):
    stop_file.write_text("")
    args = BF.build_arg_parser().parse_args(["--source", "x.com"])
    with pytest.raises(StopRequested):
        BF.run_backfill(args)


def test_reprocess_aborta_antes_de_apagar(stop_file):
    stop_file.write_text("")
    with pytest.raises(StopRequested):
        BF.reprocess(_Boom())


def test_collect_archived_feed_aborta_com_stop(stop_file):
    stop_file.write_text("")
    with pytest.raises(StopRequested):
        BF.collect_archived_feed(_Boom(), "x.com", "http://x/feed", BF.date(2026, 1, 1))


def test_run_backfill_stop_no_meio_do_laco(stop_file, monkeypatch):
    cands = [{"url": f"http://x.com/p{i}", "timestamp": f"2026010{i}000000"} for i in range(1, 5)]
    monkeypatch.setattr(BF, "_load_state", lambda: {"sources": {"x.com": {"cdx_candidates": cands, "slug_mode": "either"}}})
    monkeypatch.setattr(BF, "_save_state", lambda s: None)
    monkeypatch.setattr(BF, "fetch_robots_strict", lambda s: ("ok", "User-agent: *\nAllow: /"))
    monkeypatch.setattr(BF.time, "sleep", lambda s: None)
    monkeypatch.setattr(BF, "_engine", lambda a: object())
    fetched, ingested = [], []

    def fake_fetch(ts, url):
        fetched.append(url)
        stop_file.write_text("")  # operador cria STOP durante a execucao
        return "<html>corpo</html>"

    monkeypatch.setattr(BF, "fetch_snapshot_backoff", fake_fetch)
    monkeypatch.setattr(BF, "ingest_page", lambda e, s, u, ts, c: ingested.append(u) or {"status": "done", "offers": 0})
    args = BF.build_arg_parser().parse_args(["--source", "x.com", "--rate-limit", "0"])
    with pytest.raises(StopRequested):
        BF.run_backfill(args)
    assert len(fetched) == 1  # nenhum snapshot depois do STOP
    assert len(ingested) <= 1


def test_collect_archived_feed_stop_no_meio(stop_file, monkeypatch):
    caps = [{"timestamp": f"2026010{i}000000", "original": "http://x/feed"} for i in range(1, 5)]
    monkeypatch.setattr(BF, "fetch_robots_strict", lambda s: ("ok", "User-agent: *\nAllow: /"))
    monkeypatch.setattr(BF, "list_feed_captures", lambda *a, **k: caps)
    monkeypatch.setattr(BF, "_thin", lambda c, d: c)
    monkeypatch.setattr(BF, "_load_state", dict)
    monkeypatch.setattr(BF, "_save_state", lambda s: None)
    monkeypatch.setattr(BF.time, "sleep", lambda s: None)
    calls = []

    def fake_fetch(ts, url):
        calls.append(ts)
        stop_file.write_text("")

    monkeypatch.setattr(BF, "fetch_snapshot_backoff", fake_fetch)
    with pytest.raises(StopRequested):
        BF.collect_archived_feed(_Boom(), "x.com", "http://x/feed", BF.date(2026, 1, 1), rate_limit=0)
    assert len(calls) == 1


# ---- listener ---------------------------------------------------------------
def test_listener_run_once_aborta_com_stop(stop_file):
    stop_file.write_text("")
    with pytest.raises(StopRequested):
        FL.run_once(_Boom(), sources=[{"source": "x.com", "feed": "http://x.com/f", "mode": "titles"}],
                    http_get=lambda u: (_ for _ in ()).throw(AssertionError("rede com STOP")),
                    sleep=lambda s: None, state_path=None)


def test_listener_main_sai_com_3(stop_file, monkeypatch):
    stop_file.write_text("")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/x")
    assert FL.main(["--once", "--no-pipeline"]) == 3


def test_listener_stop_no_meio_do_laco_de_itens(stop_file, monkeypatch):
    rss = "<rss><channel>" + "".join(
        f"<item><title>Livelo Smiles bonus {i}</title><link>http://x.com/a{i}</link>"
        f"<pubDate>Mon, 01 Jun 2026 10:00:00 +0000</pubDate></item>" for i in range(5)) + "</channel></rss>"

    def http_get(url):
        if url.endswith("robots.txt"):
            return 200, "User-agent: *\nAllow: /"
        return 200, rss

    stored = []
    monkeypatch.setattr(FL, "_known", lambda e, s, u: False)

    def fake_store(engine, source, url, content, observed, pub, gap):
        stored.append(url)
        stop_file.write_text("")  # STOP criado depois da primeira gravacao
        return len(stored)

    monkeypatch.setattr(FL, "_store", fake_store)
    monkeypatch.setattr(FL.C, "process_raw_message", lambda *a, **k: [])
    monkeypatch.setattr(FL, "_record_health", lambda *a, **k: None)
    from datetime import UTC, datetime

    with pytest.raises(StopRequested):
        FL.run_source(object(), {"source": "x.com", "feed": "http://x.com/feed", "mode": "titles"},
                      http_get=http_get, sleep=lambda s: None, now=datetime(2026, 6, 2, tzinfo=UTC), state={})
    assert len(stored) == 1


# ---- DB: reprocess nao apaga; run_daily para entre grupos ---------------------
URL_DB = os.environ.get("DATABASE_URL")
needs_db = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")


@pytest.fixture
def engine():
    from sqlalchemy import text

    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=dict(os.environ))
    from preditor.api.db import get_engine

    e = get_engine()

    def wipe():
        with e.begin() as c:
            for t in ("alert", "prediction", "offer_evidence", "offer", "model_run"):
                c.execute(text(f"DELETE FROM {t}"))

    wipe()
    yield e
    wipe()


@needs_db
def test_reprocess_com_stop_nao_apaga_offer(engine, stop_file):
    from sqlalchemy import text

    stop_file.write_text("")
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) "
            "VALUES('livelo','smiles','transfer_bonus','2026-01-01',80,false,'', '2026-01-01')"))
    assert BF.main(["--reprocess", "--database-url", URL_DB]) == 3
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM offer")).scalar() == 1


@needs_db
def test_run_daily_para_entre_grupos(engine, stop_file, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    import preditor.jobs.daily_predict as DP

    with engine.begin() as c:
        for dest in ("smiles", "latam", "azul"):
            for i in range(3):
                c.execute(text(
                    "INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) "
                    "VALUES('livelo',:d,'transfer_bonus',:s,80,false,'',:s)"),
                    {"d": dest, "s": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=30 * i)})
    real = DP.predict_proba

    def predict_and_stop(**kw):
        stop_file.write_text("")  # STOP aparece durante o primeiro grupo
        return real(**kw)

    monkeypatch.setattr(DP, "predict_proba", predict_and_stop)
    with pytest.raises(StopRequested):
        DP.run_daily(as_of="2026-06-01", engine=engine)
    with engine.connect() as c:
        pairs = c.execute(text("SELECT count(DISTINCT destination) FROM prediction")).scalar()
    assert pairs == 1  # so o grupo em andamento foi gravado
