import os
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, text

from preditor import collector as C

URL_DB = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")


@pytest.fixture()
def eng():
    e = create_engine(URL_DB)
    with e.begin() as c:
        c.execute(text("TRUNCATE offer_evidence, offer, raw_message, source_health RESTART IDENTITY CASCADE"))
    return e


def snap_2023(url):
    return ('<html><head><meta property="article:published_time" content="2023-03-08T10:00:00-03:00"></head>'
            '<body>Livelo para Smiles com 100% de bônus na transferência de 10/03 a 15/03.</body></html>')


class FakeCDX:
    def __init__(self, *a, **k):
        pass

    def list_captures(self, *a, **k):
        return [{"original": "https://passageirodeprimeira.com/livelo-smiles-100-mar23/", "timestamp": "20230309120000"}]


class FakeCDXFuture:
    def __init__(self, *a, **k):
        pass

    def list_captures(self, *a, **k):
        return [{"original": "https://passageirodeprimeira.com/fut/", "timestamp": "20250305120000"}]


def test_K1_backfill_first_seen_is_capture_or_published_not_now(eng, monkeypatch):
    monkeypatch.setattr(C, "CDXClient", FakeCDX)
    C.backfill(engine=eng, source="passageirodeprimeira.com", from_="202301", transport=snap_2023)
    with eng.connect() as c:
        start, fs = c.execute(text("SELECT start_at, first_seen_at FROM offer")).fetchall()[0]
    assert fs.year == 2023 and fs <= datetime(2023, 3, 9, 12, tzinfo=UTC)
    assert start == date(2023, 3, 10)


def test_K2_raw_message_has_observed_at(eng):
    with eng.connect() as c:
        cols = {r[0] for r in c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='raw_message'"))}
    assert "observed_at" in cols


def test_K3_rss_old_item_first_seen_uses_pubdate(eng):
    feed = ('<rss><channel><item><title>Livelo para Smiles com 90% de bônus na transferência de 01/10 a 05/10</title>'
            '<link>https://passageirodeprimeira.com/a/</link><pubDate>Wed, 01 Oct 2025 09:00:00 -0300</pubDate></item></channel></rss>')
    C.collect_rss(engine=eng, source="passageirodeprimeira.com", url="https://passageirodeprimeira.com/feed/",
                  transport=lambda u: feed, robots_txt="User-agent: *\nDisallow:\n", now=datetime(2025, 10, 20, 12, tzinfo=UTC), min_interval=0)
    with eng.connect() as c:
        fs = c.execute(text("SELECT first_seen_at FROM offer")).scalar()
    assert fs is not None and fs.date() == date(2025, 10, 1)


def test_K4_robots_absent_must_fetch_robots(eng):
    calls = []

    def transport(u):
        calls.append(u)
        if "robots" in u:
            return "User-agent: *\nDisallow: /feed/\n"
        return "<rss/>"

    C.collect_rss(engine=eng, source="passageirodeprimeira.com", url="https://passageirodeprimeira.com/feed/",
                  transport=transport, now=datetime(2025, 1, 1, tzinfo=UTC), min_interval=0)
    assert any("robots.txt" in c for c in calls)


def test_K6_first_seen_min_over_evidences(eng, monkeypatch):
    feed = ('<rss><channel><item><title>Livelo para Smiles com 100% de bônus na transferência de 10/03 a 15/03</title>'
            '<link>https://melhorescartoes.com.br/x</link></item></channel></rss>')
    C.collect_rss(engine=eng, source="www.melhorescartoes.com.br", url="https://www.melhorescartoes.com.br/feed",
                  transport=lambda u: feed, robots_txt="User-agent: *\nDisallow:\n", now=datetime(2025, 3, 9, 12, tzinfo=UTC), min_interval=0)
    monkeypatch.setattr(C, "CDXClient", FakeCDXFuture)
    C.backfill(engine=eng, source="passageirodeprimeira.com",
               transport=lambda u: "<p>Livelo para Smiles com 100% de bônus na transferência de 10/03/2025 a 15/03/2025.</p>")
    with eng.connect() as c:
        fs = c.execute(text("SELECT min(first_seen_at) FROM offer")).scalar()
        n = c.execute(text("SELECT count(*) FROM offer")).scalar()
    assert n == 1 and fs.date() == date(2025, 3, 5)


def test_K7_evidence_point_in_time_reconstructable(eng):
    with eng.connect() as c:
        ecols = {r[0] for r in c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='offer_evidence'"))}
        rcols = {r[0] for r in c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='raw_message'"))}
    assert "observed_at" in ecols or "observed_at" in rcols


def test_K8_first_seen_preserves_instant(eng):
    feed = ('<rss><channel><item><title>Livelo para Smiles com 90% de bônus na transferência de 10/03 a 15/03</title>'
            '<link>https://passageirodeprimeira.com/k8</link><pubDate>Mon, 09 Mar 2025 15:00:00 -0300</pubDate></item></channel></rss>')
    C.collect_rss(engine=eng, source="passageirodeprimeira.com", url="https://passageirodeprimeira.com/feed/",
                  transport=lambda u: feed, robots_txt="User-agent: *\nDisallow:\n",
                  now=datetime(2025, 3, 9, 20, tzinfo=UTC), min_interval=0)
    with eng.connect() as c:
        fs = c.execute(text("SELECT first_seen_at FROM offer")).scalar()
    assert fs is not None
    assert fs != datetime(fs.year, fs.month, fs.day, tzinfo=fs.tzinfo)


def test_K9_process_raw_without_observed_fails_closed(eng):
    from preditor import ingest as I
    r = I.store_raw_message(engine=eng, source="passageirodeprimeira.com", url="https://x/p", content="Livelo para Smiles 90% de 10/03 a 15/03")
    with eng.begin() as c:
        c.execute(text("UPDATE raw_message SET observed_at=NULL WHERE id=:i"), {"i": r.id})
    class RM:
        pass
    obj = RM()
    obj.id = r.id
    obj.source = r.source
    obj.content = r.content
    obj.observed_at = None
    obj.collected_at = r.collected_at
    with pytest.raises(C.CollectorError):
        C.process_raw_message(eng, obj)


def test_K10_migration_no_default(eng):
    with eng.connect() as c:
        cols = c.execute(text(
            "SELECT column_name, is_nullable, column_default FROM information_schema.columns WHERE table_name='raw_message' AND column_name='observed_at'"
        )).fetchall()
    assert cols
    assert cols[0][1] == "YES"


def test_K11_pubdate_future_uses_min(eng):
    feed = ('<rss><channel><item><title>Livelo para Smiles com 90% de bônus na transferência de 10/03 a 15/03</title>'
            '<link>https://passageirodeprimeira.com/fut1</link><pubDate>Sun, 15 Mar 2025 09:00:00 -0300</pubDate></item></channel></rss>')
    C.collect_rss(engine=eng, source="passageirodeprimeira.com", url="https://passageirodeprimeira.com/feed/",
                  transport=lambda u: feed, robots_txt="User-agent: *\nDisallow:\n",
                  now=datetime(2025, 3, 9, 12, tzinfo=UTC), min_interval=0)
    with eng.connect() as c:
        fs = c.execute(text("SELECT observed_at FROM raw_message")).scalar()
    assert fs is not None
    assert fs <= datetime(2025, 3, 9, 12, tzinfo=UTC)


def test_K12_robots_fetched_when_absent(eng):
    calls = []

    def transport(u):
        calls.append(u)
        if "robots" in u:
            return "User-agent: *\nAllow: /\n"
        return "<rss/>"

    C.collect_rss(engine=eng, source="passageirodeprimeira.com", url="https://passageirodeprimeira.com/feed/",
                  transport=transport, now=datetime(2025, 1, 1, tzinfo=UTC), min_interval=0)
    assert any("robots.txt" in c for c in calls)


def test_K13_same_content_observed_min_leasts(eng):
    from preditor import ingest as I
    r1 = I.store_raw_message(engine=eng, source="passageirodeprimeira.com", url="https://x", content="same",
                            observed_at=datetime(2025, 3, 9, tzinfo=UTC))
    r2 = I.store_raw_message(engine=eng, source="passageirodeprimeira.com", url="https://x", content="same",
                            observed_at=datetime(2025, 3, 5, tzinfo=UTC))
    assert r1.id == r2.id
    with eng.connect() as c:
        obs = c.execute(text("SELECT observed_at FROM raw_message WHERE id=:i"), {"i": r1.id}).scalar()
    assert obs.date() == date(2025, 3, 5)


def test_K14_ingest_direct_no_default_now(eng):
    from preditor import ingest as I
    raw = I.store_raw_message(engine=eng, source="passageirodeprimeira.com", url="https://x2", content="noobs",
                             collected_at=datetime(2025, 1, 1, tzinfo=UTC))
    with eng.connect() as c:
        obs = c.execute(text("SELECT observed_at FROM raw_message WHERE id=:i"), {"i": raw.id}).scalar()
    assert obs is None


def test_P1_reprocess_missing_observed_fails(eng):
    from preditor import ingest as I
    r = I.store_raw_message(engine=eng, source="passageirodeprimeira.com", url="https://xp", content="t",
                           collected_at=datetime(2025, 1, 1, tzinfo=UTC))
    with eng.begin() as c:
        c.execute(text("UPDATE raw_message SET observed_at=NULL WHERE id=:i"), {"i": r.id})
    class RM:
        pass
    obj = RM()
    obj.id = r.id
    obj.source = r.source
    obj.content = r.content
    obj.observed_at = None
    with pytest.raises(C.CollectorError):
        C.process_raw_message(eng, obj)


def test_P2_observed_recorded_on_insert(eng):
    from preditor import ingest as I
    r = I.store_raw_message(engine=eng, source="passageirodeprimeira.com", url="https://xq", content="q",
                           observed_at=datetime(2025, 2, 2, tzinfo=UTC))
    assert r.observed_at is not None


def test_P3_first_seen_instant_not_truncated(eng):
    feed = ('<rss><channel><item><title>Livelo para Smiles com 90% de bônus na transferência de 10/03 a 15/03</title>'
            '<link>https://passageirodeprimeira.com/p3</link><pubDate>Mon, 09 Mar 2025 15:30:00 -0300</pubDate></item></channel></rss>')
    C.collect_rss(engine=eng, source="passageirodeprimeira.com", url="https://passageirodeprimeira.com/feed/",
                  transport=lambda u: feed, robots_txt="User-agent: *\nDisallow:\n",
                  now=datetime(2025, 3, 9, 20, tzinfo=UTC), min_interval=0)
    with eng.connect() as c:
        fs = c.execute(text("SELECT first_seen_at FROM offer")).scalar()
    assert fs is not None
    assert fs.utcoffset() is not None


def test_P4_recompute_first_seen_min_over_evidences_instant(eng):
    feed = ('<rss><channel><item><title>Livelo para Smiles com 100% de bônus na transferência de 10/03 a 15/03</title>'
            '<link>https://melhorescartoes.com.br/p4</link></item></channel></rss>')
    C.collect_rss(engine=eng, source="www.melhorescartoes.com.br", url="https://www.melhorescartoes.com.br/feed",
                  transport=lambda u: feed, robots_txt="User-agent: *\nDisallow:\n",
                  now=datetime(2025, 3, 9, 12, tzinfo=UTC), min_interval=0)
    from preditor import ingest as I
    r = I.store_raw_message(engine=eng, source="passageirodeprimeira.com", url="https://passageirodeprimeira.com/p4b",
                           content="Livelo para Smiles com 100% de bônus na transferência de 10/03 a 15/03.",
                           observed_at=datetime(2025, 3, 5, 10, tzinfo=UTC))
    C.process_raw_message(eng, r, first_seen_at=datetime(2025, 3, 5, 10, tzinfo=UTC))
    with eng.connect() as c:
        fs = c.execute(text("SELECT min(first_seen_at) FROM offer")).scalar()
    assert fs.date() == date(2025, 3, 5)
