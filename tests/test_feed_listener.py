"""Listener recorrente de feeds: idempotente, robots fail-closed, 1 req/10 s, source_health."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from preditor.jobs import feed_listener as FL

URL_DB = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")

NOW = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
FEED = """<rss><channel>
<item><title>Smiles oferece até 100% de bônus nas transferências da Livelo</title>
<link>https://passageirodeprimeira.com/a-1/</link><pubDate>Wed, 14 Oct 2026 12:00:00 +0000</pubDate>
<description>RESUMO LONGO</description></item>
<item><title>Voo barato</title><link>https://passageirodeprimeira.com/a-2/</link>
<pubDate>Mon, 01 Jan 2026 12:00:00 +0000</pubDate></item>
</channel></rss>"""
ARTICLE = ("<html><body><article><p>A Smiles está oferecendo até 100% de bônus nas transferências de pontos da "
           "Livelo. A oferta é válida somente até hoje (14).</p></article></body></html>")
SRC = {"source": "passageirodeprimeira.com", "feed": "https://passageirodeprimeira.com/feed/", "mode": "article"}
PPV = {"source": "pontospravoar.com", "feed": "https://pontospravoar.com/feed/", "mode": "titles"}


@pytest.fixture
def eng(db_at_head):
    e = create_engine(URL_DB)

    def clean():
        with e.begin() as c:
            for t in ("offer_evidence", "offer", "raw_message", "source_health"):
                c.execute(text(f"DELETE FROM {t}"))

    clean()
    yield e
    clean()


class Net:
    def __init__(self, robots=(200, "User-agent: *\nAllow: /\n"), feed=(200, FEED), article=(200, ARTICLE)):
        self.robots, self.feed, self.article = robots, feed, article
        self.calls: list[str] = []
        self.sleeps: list[float] = []

    def get(self, url):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return self.robots
        if "/feed" in url:
            return self.feed
        if "/a-2/" in url:
            return 200, "<html><body><article><p>Dicas de voo barato.</p></article></body></html>"
        return self.article

    def sleep(self, s):
        self.sleeps.append(s)


def _run(eng, net, cfg=SRC, now=NOW):
    return FL.run_once(eng, sources=[cfg], http_get=net.get, sleep=net.sleep, now=now, run_pipeline=False)


def _count(eng, table):
    with eng.connect() as c:
        return c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_collects_items_and_extracts_offer(eng):
    net = Net()
    out = _run(eng, net)
    assert out["passageirodeprimeira.com"]["items_new"] == 2
    assert _count(eng, "raw_message") == 2
    assert _count(eng, "offer") == 1


def test_idempotent_second_run_adds_nothing_and_skips_article_fetch(eng):
    _run(eng, Net())
    net2 = Net()
    out = _run(eng, net2)
    assert out["passageirodeprimeira.com"]["items_new"] == 0
    assert _count(eng, "raw_message") == 2 and _count(eng, "offer") == 1
    assert not [u for u in net2.calls if "/a-" in u]


def test_robots_unavailable_fails_closed(eng):
    net = Net(robots=(503, ""))
    out = _run(eng, net)
    assert out["passageirodeprimeira.com"]["status"] == "robots_unavailable"
    assert [u for u in net.calls if not u.endswith("/robots.txt")] == []
    with eng.connect() as c:
        row = c.execute(text("SELECT alert, items_new FROM source_health")).one()
    assert row[0] is True and row[1] == 0


def test_robots_blocks_article_url(eng):
    net = Net(robots=(200, "User-agent: *\nDisallow: /a-1/\n"))
    _run(eng, net)
    assert not [u for u in net.calls if u.endswith("/a-1/")]


def test_min_10s_between_requests_to_same_domain(eng):
    net = Net()
    _run(eng, net)
    assert len(net.sleeps) >= 3 and all(s >= 10.0 for s in net.sleeps)


def test_titles_mode_never_fetches_article_body(eng):
    feed = FEED.replace("passageirodeprimeira.com", "pontospravoar.com")
    net = Net(feed=(200, feed))
    _run(eng, net, cfg=PPV)
    assert [u for u in net.calls if "/a-" in u] == []
    with eng.connect() as c:
        contents = c.execute(text("SELECT content FROM raw_message")).scalars().all()
    assert all("RESUMO" not in x for x in contents)


def test_old_items_flagged_with_gap(eng):
    _run(eng, Net())
    with eng.connect() as c:
        rows = dict(c.execute(text("SELECT url, published_vs_capture_gap FROM raw_message")).all())
    assert rows["https://passageirodeprimeira.com/a-1/"] is False
    assert rows["https://passageirodeprimeira.com/a-2/"] is True


def test_source_health_row_written_with_status_and_failures(eng):
    _run(eng, Net(feed=(500, "")))
    _run(eng, Net(feed=(500, "")), now=NOW + timedelta(hours=1))
    st = FL.source_status(eng, now=NOW + timedelta(hours=2))["passageirodeprimeira.com"]
    assert st["consecutive_failures"] == 2
    assert st["last_success_at"] is None
    _run(eng, Net(), now=NOW + timedelta(hours=3))
    st = FL.source_status(eng, now=NOW + timedelta(hours=4))["passageirodeprimeira.com"]
    assert st["consecutive_failures"] == 0 and st["last_success_at"] is not None
    assert st["delay_hours"] == pytest.approx(7.0)  # 19:00 - ultimo item observado as 12:00


def test_api_source_health_reports_status_last_item_and_failures(eng):
    from preditor.api.queries import fetch_source_health

    _run(eng, Net())  # ok, 1 item novo
    for h in (1, 2, 3):
        _run(eng, Net(feed=(500, "")), now=NOW + timedelta(hours=h))
    src = {s["source"]: s for s in fetch_source_health()["sources"]}["passageirodeprimeira.com"]
    assert src["status"] == "error"          # 3 falhas seguidas
    assert src["last_item_at"] is not None
    assert src["last_success_at"].startswith("2026-10-14T15:00:00")
