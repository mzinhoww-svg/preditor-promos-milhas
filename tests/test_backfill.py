"""Backfill Wayback: retomavel, idempotente, robots fail-closed, ritmo e ponto-no-tempo."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from preditor import backfill as B

URLS = [
    {"url": "http://a.com/p1", "timestamp": "20240105120000"},
    {"url": "http://a.com/p2", "timestamp": "20240210120000"},
]
ROBOTS_OK = "User-agent: *\nAllow: /\n"


def _args(**kw):
    base = {"sources": ["a.com"], "from_": "202301", "to": None, "rate_limit": 10.0, "page_size": 50,
            "database_url": "sqlite://", "refresh_candidates": False, "titles_only": False,
            "max_attempts": 3, "slug_mode": "both"}
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(B, "STATE_PATH", tmp_path / "state.json")
    sleeps, fetched = [], []
    monkeypatch.setattr(B.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(B, "fetch_robots_strict", lambda source: ("ok", ROBOTS_OK))
    monkeypatch.setattr(B, "fetch_cdx_candidates", lambda *a, **k: list(URLS))

    def fake_fetch(ts, url):
        fetched.append(url)
        return "<html>ok</html>"

    monkeypatch.setattr(B, "fetch_snapshot_backoff", fake_fetch)
    monkeypatch.setattr(B, "ingest_page", lambda *a, **k: {"status": "done", "offers": 1, "raw_id": 1, "gap": False})
    return type("E", (), {"sleeps": sleeps, "fetched": fetched, "mp": monkeypatch})


def test_resume_does_not_refetch_done(env):
    B.run_backfill(_args())
    assert len(env.fetched) == 2
    B.run_backfill(_args())
    assert len(env.fetched) == 2


def test_sleeps_rate_limit_before_each_snapshot(env):
    B.run_backfill(_args(rate_limit=10.0))
    assert env.sleeps.count(10.0) >= 2


def test_robots_unavailable_aborts_source_fail_closed(env):
    env.mp.setattr(B, "fetch_robots_strict", lambda source: ("robots_unavailable", None))
    out = B.run_backfill(_args())
    assert env.fetched == []
    assert out["summary"]["a.com"]["status"] == "robots_unavailable"


def test_robots_root_disallow_aborts_without_fetch(env):
    env.mp.setattr(B, "fetch_robots_strict", lambda source: ("ok", "User-agent: *\nDisallow: /\n"))
    out = B.run_backfill(_args())
    assert env.fetched == []
    assert out["summary"]["a.com"]["status"] == "robots_disallowed"


def test_robots_checked_per_candidate_url(env):
    env.mp.setattr(B, "fetch_robots_strict", lambda source: ("ok", "User-agent: *\nDisallow: /p2\n"))
    B.run_backfill(_args())
    assert env.fetched == ["http://a.com/p1"]
    st = B._load_state()["sources"]["a.com"]["processed"]
    assert st["http://a.com/p2"]["status"] == "robots_disallowed"


def test_robots_hash_recorded_for_every_source(env):
    env.mp.setattr(B, "fetch_cdx_candidates", lambda *a, **k: [])
    env.mp.setattr(B, "fetch_robots_strict",
                   lambda s: ("robots_unavailable", None) if s == "b.com" else ("ok", ROBOTS_OK))
    B.run_backfill(_args(sources=["a.com", "b.com"]))
    srcs = B._load_state()["sources"]
    assert srcs["a.com"]["robots_hash"]
    assert srcs["b.com"]["robots_status"] == "robots_unavailable"
    assert "robots_hash" in srcs["b.com"]


def test_sleeps_at_least_rate_limit_between_sources(env):
    env.mp.setattr(B, "fetch_cdx_candidates", lambda *a, **k: [])
    B.run_backfill(_args(sources=["a.com", "b.com"], rate_limit=10.0))
    assert env.sleeps and min(env.sleeps) >= 10.0


def test_failed_fetch_retried_only_up_to_max_attempts(env):
    env.mp.setattr(B, "fetch_snapshot_backoff", lambda ts, url: env.fetched.append(url))
    for _ in range(5):
        B.run_backfill(_args(max_attempts=3))
    assert len(env.fetched) == 2 * 3


def test_error_status_also_limited_by_max_attempts(env):
    env.mp.setattr(B, "ingest_page", lambda *a, **k: {"status": "error", "error": "boom"})
    for _ in range(5):
        B.run_backfill(_args(max_attempts=2))
    assert len(env.fetched) == 2 * 2


def test_failed_then_success_marks_done(env):
    calls = {"n": 0}

    def flaky(ts, url):
        calls["n"] += 1
        return None if calls["n"] <= 2 else "<html>ok</html>"

    env.mp.setattr(B, "fetch_snapshot_backoff", flaky)
    B.run_backfill(_args())
    out = B.run_backfill(_args())
    assert out["summary"]["a.com"]["processed_done"] == 2


# --- robots real (redirects) ---------------------------------------------------------
def _client(handler):
    return lambda: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_fetch_robots_follows_redirect(monkeypatch):
    def handler(req: httpx.Request):
        if req.url.scheme == "http":
            return httpx.Response(301, headers={"location": "https://www.a.com/robots.txt"})
        return httpx.Response(200, text="User-agent: *\nDisallow: /x\n")

    monkeypatch.setattr(B, "_new_client", _client(handler))
    st, txt = B.fetch_robots_strict("a.com")
    assert st == "ok" and "Disallow: /x" in txt


def test_fetch_robots_403_is_unavailable(monkeypatch):
    monkeypatch.setattr(B, "_new_client", _client(lambda r: httpx.Response(403)))
    assert B.fetch_robots_strict("a.com") == ("robots_unavailable", None)


def test_fetch_robots_404_means_no_restrictions(monkeypatch):
    monkeypatch.setattr(B, "_new_client", _client(lambda r: httpx.Response(404)))
    assert B.fetch_robots_strict("a.com") == ("ok", "")


# --- snapshot com backoff em 429 ---------------------------------------------------------
def test_snapshot_backoff_on_429(monkeypatch):
    seq = [429, 429, 200]
    sleeps = []
    monkeypatch.setattr(B.time, "sleep", lambda s: sleeps.append(s))

    def handler(req):
        code = seq.pop(0)
        return httpx.Response(code, text="<html>x</html>")

    monkeypatch.setattr(B, "_new_client", _client(handler))
    assert B.fetch_snapshot_backoff("20240101000000", "http://a.com/p") == "<html>x</html>"
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]


# --- ponto-no-tempo / ingest_page ---------------------------------------------------------
HTML = ('<html><head><meta property="article:published_time" content="2023-01-01T10:00:00+00:00"></head>'
        "<body><article><p>Livelo para Smiles com 100% de bônus até 31/01.</p></article></body></html>")


@pytest.fixture
def ing(monkeypatch):
    calls = {"stored": [], "gap": [], "proc": []}

    def store_raw(**k):
        calls["stored"].append(k)
        return type("R", (), {"id": 7})()

    monkeypatch.setattr(B.C, "store_raw", store_raw)
    monkeypatch.setattr(B, "_mark_gap", lambda eng, rid, pub, gap: calls["gap"].append((rid, pub, gap)))
    monkeypatch.setattr(B.C, "process_raw_message",
                        lambda eng, raw, first_seen_at=None, **k: calls["proc"].append((raw["content"], first_seen_at)) or [1])
    return calls


def test_gap_flag_when_published_more_than_7_days_before_capture(ing):
    r = B.ingest_page(object(), "a.com", "http://a.com/p", "20240401000000", HTML)
    assert r["gap"] is True
    assert ing["gap"][0][2] is True


def test_no_gap_flag_when_published_close_to_capture(ing):
    close = HTML.replace("2023-01-01", "2024-03-30")
    r = B.ingest_page(object(), "a.com", "http://a.com/p", "20240401000000", close)
    assert r["gap"] is False


def test_no_dates_at_all_is_not_stored(ing, monkeypatch):
    monkeypatch.setattr(B.C, "_ts_to_datetime", lambda ts: None)
    r = B.ingest_page(object(), "a.com", "http://a.com/p", "garbage", "<html>sem data</html>")
    assert r["status"] == "skipped_no_date"
    assert ing["stored"] == []


def test_only_article_snippets_are_extracted(ing):
    B.ingest_page(object(), "a.com", "http://a.com/p", "20240401000000", HTML)
    assert len(ing["proc"]) == 1
    assert "100%" in ing["proc"][0][0] and "<" not in ing["proc"][0][0]


def test_normalize_candidate_strips_noise():
    assert B._normalize_candidate({"original": "http://a.com/x/feed/", "timestamp": "1"}) == (None, None)
    u, _ = B._normalize_candidate({"original": "http://a.com/x/?utm=1", "timestamp": "2024"})
    assert u is not None and "?" not in u


def test_observed_never_after_capture():
    pub = datetime(2024, 5, 1, tzinfo=UTC)
    cap = pub - timedelta(days=3)
    assert B._observed(pub, cap) == cap


def test_rss_titles_only_requires_robots_ok(monkeypatch):
    monkeypatch.setattr(B, "fetch_robots_strict", lambda source: ("robots_unavailable", None))
    called = []
    monkeypatch.setattr(B.C, "collect_rss", lambda **k: called.append(k) or [])
    assert B.collect_titles_rss(object(), "pontospravoar.com", "https://pontospravoar.com/feed/")["status"] == "robots_unavailable"
    assert called == []


def test_rss_titles_only_passes_robots_text_and_url_check(monkeypatch):
    monkeypatch.setattr(B, "fetch_robots_strict", lambda source: ("ok", "User-agent: *\nDisallow: /feed/\n"))
    called = []
    monkeypatch.setattr(B.C, "collect_rss", lambda **k: called.append(k) or [])
    out = B.collect_titles_rss(object(), "pontospravoar.com", "https://pontospravoar.com/feed/")
    assert out["status"] == "robots_disallowed" and called == []
    monkeypatch.setattr(B, "fetch_robots_strict", lambda source: ("ok", ROBOTS_OK))
    out = B.collect_titles_rss(object(), "pontospravoar.com", "https://pontospravoar.com/feed/")
    assert out["status"] == "ok" and len(called) == 1 and called[0]["robots_txt"] == ROBOTS_OK


# --- RSS arquivado (so titulo/data/link, decisao 002) -------------------------------------
FEED = """<rss><channel>
<item><title>Livelo e Smiles: 100% de bônus até 30/09</title><link>https://pontospravoar.com/a/</link>
<pubDate>Mon, 25 Sep 2023 10:00:00 +0000</pubDate><description>CORPO PROIBIDO</description></item>
</channel></rss>"""


@pytest.fixture
def feed(monkeypatch, tmp_path):
    monkeypatch.setattr(B, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(B.time, "sleep", lambda s: None)
    monkeypatch.setattr(B, "fetch_robots_strict", lambda s: ("ok", ROBOTS_OK))
    caps = [{"timestamp": f"2023092{i}120000", "original": "https://pontospravoar.com/feed/"} for i in range(1, 10)]
    monkeypatch.setattr(B, "list_feed_captures", lambda *a, **k: caps)
    rec = {"fetched": [], "stored": [], "proc": []}
    monkeypatch.setattr(B, "fetch_snapshot_backoff", lambda ts, u: rec["fetched"].append(ts) or FEED)
    monkeypatch.setattr(B.C, "store_raw", lambda **k: rec["stored"].append(k) or type("R", (), {"id": len(rec["stored"])})())
    monkeypatch.setattr(B, "_mark_gap", lambda *a: None)
    monkeypatch.setattr(B.C, "process_raw_message", lambda e, raw, first_seen_at=None, **k: rec["proc"].append(raw) or [1])
    return rec


def test_archived_feed_stores_only_title_never_description(feed):
    out = B.collect_archived_feed(object(), "pontospravoar.com", "https://pontospravoar.com/feed/",
                                  date(2023, 1, 1), rate_limit=10.0, step_days=5)
    assert out["status"] == "ok"
    assert feed["stored"] and all("CORPO" not in k["content"] for k in feed["stored"])
    assert feed["stored"][0]["content"].startswith("Livelo e Smiles")
    assert feed["stored"][0]["observed_at"] <= datetime(2023, 9, 25, 10, 0, tzinfo=UTC)


def test_archived_feed_thins_captures_and_is_resumable(feed):
    B.collect_archived_feed(object(), "pontospravoar.com", "https://pontospravoar.com/feed/",
                            date(2023, 1, 1), rate_limit=10.0, step_days=5)
    n1 = len(feed["fetched"])
    assert 0 < n1 < 9
    B.collect_archived_feed(object(), "pontospravoar.com", "https://pontospravoar.com/feed/",
                            date(2023, 1, 1), rate_limit=10.0, step_days=5)
    assert len(feed["fetched"]) == n1


def test_archived_feed_respects_robots(feed, monkeypatch):
    monkeypatch.setattr(B, "fetch_robots_strict", lambda s: ("ok", "User-agent: *\nDisallow: /feed/\n"))
    out = B.collect_archived_feed(object(), "pontospravoar.com", "https://pontospravoar.com/feed/",
                                  date(2023, 1, 1), rate_limit=10.0, step_days=5)
    assert out["status"] == "robots_disallowed" and feed["fetched"] == []
