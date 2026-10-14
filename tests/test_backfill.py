"""Backfill Wayback: retomavel, idempotente, respeita robots e ritmo."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime

import pytest

from preditor import backfill as B

URLS = [
    {"url": "http://a.com/p1", "timestamp": "20240105120000"},
    {"url": "http://a.com/p2", "timestamp": "20240210120000"},
]


def _args(**kw):
    base = {"sources": ["a.com"], "from_": "202301", "to": None, "rate_limit": 10.0, "page_size": 50,
                "database_url": "sqlite://", "refresh_candidates": False, "titles_only": False, "max_attempts": 3}
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(B, "STATE_PATH", tmp_path / "state.json")
    sleeps, fetched = [], []
    monkeypatch.setattr(B.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(B.C, "fetch_robots", lambda *a, **k: "User-agent: *\nAllow: /\n")
    monkeypatch.setattr(B, "fetch_cdx_candidates", lambda *a, **k: list(URLS))
    monkeypatch.setattr(B.C, "_extract_published_time", lambda c: None)
    monkeypatch.setattr(B.C, "_ts_to_datetime", lambda ts: datetime(2024, 1, 5, tzinfo=UTC))
    monkeypatch.setattr(B.C, "store_raw", lambda **k: type("R", (), {"id": 1})())
    monkeypatch.setattr(B.C, "process_raw_message", lambda *a, **k: [object()])

    def fake_fetch(ts, url, transport=None):
        fetched.append(url)
        return "<html>ok</html>"

    monkeypatch.setattr(B.C, "fetch_snapshot", fake_fetch)
    return type("E", (), {"sleeps": sleeps, "fetched": fetched, "mp": monkeypatch})


def test_resume_does_not_refetch_done(env):
    B.run_backfill(_args())
    assert len(env.fetched) == 2
    B.run_backfill(_args())
    assert len(env.fetched) == 2  # idempotente: nada novo


def test_sleeps_rate_limit_before_each_snapshot(env):
    B.run_backfill(_args(rate_limit=10.0))
    assert env.sleeps.count(10.0) >= 2


def test_robots_block_aborts_without_fetch(env):
    env.mp.setattr(B.C, "fetch_robots", lambda *a, **k: "User-agent: *\nDisallow: /\n")
    with pytest.raises(SystemExit):
        B.run_backfill(_args())
    assert env.fetched == []


def test_failed_fetch_retried_only_up_to_max_attempts(env):
    env.mp.setattr(B.C, "fetch_snapshot", lambda ts, url, transport=None: env.fetched.append(url))
    for _ in range(5):
        B.run_backfill(_args(max_attempts=3))
    assert len(env.fetched) == 2 * 3


def test_failed_then_success_marks_done(env):
    calls = {"n": 0}

    def flaky(ts, url, transport=None):
        calls["n"] += 1
        return None if calls["n"] <= 2 else "<html>ok</html>"

    env.mp.setattr(B.C, "fetch_snapshot", flaky)
    B.run_backfill(_args())
    out = B.run_backfill(_args())
    assert out["summary"]["a.com"]["processed_done"] == 2


def test_normalize_candidate_strips_noise():
    assert B._normalize_candidate({"original": "http://a.com/x/feed/", "timestamp": "1"}) == (None, None)
    u, _ = B._normalize_candidate({"original": "http://a.com/x/?utm=1", "timestamp": "2024"})
    assert u is not None and "?" not in u
