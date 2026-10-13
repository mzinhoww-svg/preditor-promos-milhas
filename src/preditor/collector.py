from __future__ import annotations

"""Coletor Livelo -> Smiles: RSS, backfill Wayback, pipeline raw -> offer/evidence."""
import hashlib
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from urllib.robotparser import RobotFileParser

from preditor.campaigns import Evidence, consolidate
from preditor.extract import extract
from preditor.ingest import store_raw_message
from preditor.wayback import DEFAULT_USER_AGENT, CDXClient, RateLimiter

UA = DEFAULT_USER_AGENT
RATE_LIMIT_SEC = 10.0
SOURCES = {
    "passageirodeprimeira.com": {"collect_body": True},
    "www.melhorescartoes.com.br": {"collect_body": True},
    "pontospravoar.com": {"collect_body": False},
}


def _engine_from(kwargs):
    for key in ("engine", "db", "database", "connection", "conn", "session"):
        if key in kwargs and kwargs[key] is not None:
            return kwargs.pop(key)
    return None


def _now(kwargs):
    for key in ("now", "reference", "as_of", "timestamp"):
        if key in kwargs and kwargs[key] is not None:
            v = kwargs.pop(key)
            if isinstance(v, str):
                try:
                    return datetime.fromisoformat(v)
                except ValueError:
                    return v
            return v
    return datetime.now(UTC)


def _to_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            try:
                return datetime.fromisoformat(v).date()
            except ValueError:
                return None
    return None


def robots_allowed(robots_txt, url):
    rp = RobotFileParser()
    try:
        rp.parse((robots_txt or "").splitlines())
    except Exception:  # noqa: BLE001
        return True
    try:
        return rp.can_fetch(UA, url)
    except Exception:  # noqa: BLE001
        return True


def parse_feed(xml_text):
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for el in root.iter():
        if not el.tag.lower().endswith("item"):
            continue
        obj = {}
        for child in el:
            tag = child.tag.split("}")[-1].lower()
            obj[tag] = (child.text or "").strip()
        link = obj.get("link")
        if not link:
            continue
        items.append({
            "title": obj.get("title"),
            "link": link,
            "pubDate": obj.get("pubdate") or obj.get("published") or obj.get("date"),
            "description": obj.get("description") or obj.get("summary"),
            "guid": obj.get("guid"),
        })
    return items


def content_hash(value):
    if isinstance(value, bytes):
        data = value
    elif isinstance(value, str):
        data = value.encode()
    else:
        data = str(value).encode()
    return hashlib.sha256(data).hexdigest()


class RateLimitState:
    def __init__(self, min_interval=RATE_LIMIT_SEC):
        self.rl = RateLimiter(min_interval=min_interval)

    def wait(self):
        self.rl.wait()


def fetch_url(url, transport=None, rate_limiter=None, robots_txt=None):
    if robots_txt is not None and not robots_allowed(robots_txt, url):
        return None
    if rate_limiter is not None:
        try:
            rate_limiter.wait()
        except Exception:  # noqa: BLE001, S110
            pass
    if transport is not None:
        try:
            if hasattr(transport, "fetch"):
                return transport.fetch(url)
            return transport(url)
        except Exception:  # noqa: BLE001
            try:
                import httpx
                client = httpx.Client(transport=transport, headers={"User-Agent": UA})
                resp = client.get(url)
                return resp.text if hasattr(resp, "text") else str(resp)
            except Exception:  # noqa: BLE001
                return None
    return None


def store_raw(engine, source, url, content, collected_at=None):
    return store_raw_message(engine=engine, source=source, url=url, content=content, collected_at=collected_at)


def _extract_field(raw, field, kwargs):
    if hasattr(raw, field):
        return getattr(raw, field)
    return kwargs.get(field)


def process_raw_message(engine, raw_message, first_seen_at=None, **kwargs):
    content = _extract_field(raw_message, "content", kwargs)
    rm_id = kwargs.get("raw_message_id", kwargs.get("id"))
    if rm_id is None:
        rm_id = getattr(raw_message, "id", None)
    source = _extract_field(raw_message, "source", kwargs)
    source = source if source is not None else kwargs.get("source")
    if first_seen_at is None and hasattr(raw_message, "collected_at"):
        first_seen_at = getattr(raw_message, "collected_at", None)
    fs = first_seen_at if first_seen_at is not None else kwargs.get("first_seen_at")
    text_content = content if isinstance(content, str) else str(content or "")

    extraction = extract(text_content, first_seen_at=fs)
    created = []
    for off in extraction.ofertas:
        start_iso = off.inicio
        if start_iso is None and fs is not None:
            fsd = fs.date() if hasattr(fs, "date") else _to_date(fs)
            start_iso = fsd.isoformat() if fsd else None
        if start_iso is None:
            continue
        origin = off.origem
        destination = off.destino
        etype = off.tipo
        bonus = off.bonus_pct
        segmented = bool(off.segmentada)
        segment_label = off.segmento or ""
        start_date = date.fromisoformat(start_iso)
        fs_date = fs.date() if hasattr(fs, "date") else _to_date(fs)
        first_seen_val = fs_date or start_date

        offer_id = _find_offer(engine, origin, destination, etype, segmented, segment_label, start_date)
        if offer_id is None:
            offer_id = _insert_offer(engine, origin, destination, etype, start_date, off.fim, bonus, segmented, segment_label, first_seen_val)
        _insert_evidence(engine, offer_id, rm_id, source, start_date)
        _recompute_offer(engine, offer_id)
        created.append(offer_id)
    return created


def _find_offer(engine, origin, destination, etype, segmented, segment_label, start_date):
    try:
        with engine.connect() as c:
            from sqlalchemy import text
            rows = c.execute(text(
                "SELECT id, start_at FROM offer WHERE origin=:o AND destination=:d AND event_type=:t "
                "AND segmented=:s AND segment_label=:l"
            ), {"o": origin, "d": destination, "t": etype, "s": segmented, "l": segment_label}).fetchall()
        for r in rows:
            oid = r[0] if not hasattr(r, "id") else r.id
            sd = r[1] if not hasattr(r, "start_at") else r.start_at
            if isinstance(sd, str):
                sd = date.fromisoformat(sd)
            if abs((sd - start_date).days) <= 3:
                return int(oid)
    except Exception:  # noqa: BLE001
        return None
    return None


def _insert_offer(engine, origin, destination, etype, start_date, end_date, bonus, segmented, segment_label, first_seen):
    end_iso = end_date.isoformat() if hasattr(end_date, "isoformat") else end_date
    with engine.begin() as c:
        from sqlalchemy import text
        c.execute(text(
            "INSERT INTO offer(origin,destination,event_type,start_at,end_at,bonus_pct,segmented,segment_label,first_seen_at) "
            "VALUES (:o,:d,:t,:s,:e,:b,:seg,:sl,:fs) ON CONFLICT DO NOTHING"
        ), {"o": origin, "d": destination, "t": etype, "s": start_date, "e": end_iso,
            "b": bonus, "seg": segmented, "sl": segment_label, "fs": first_seen})
        rid = c.execute(text(
            "SELECT id FROM offer WHERE origin=:o AND destination=:d AND event_type=:t AND start_at=:s AND segmented=:seg AND segment_label=:sl"
        ), {"o": origin, "d": destination, "t": etype, "s": start_date, "seg": segmented, "sl": segment_label}).scalar_one()
    return int(rid)


def _insert_evidence(engine, offer_id, raw_message_id, source, seen_start):
    if raw_message_id is None:
        return
    try:
        with engine.begin() as c:
            from sqlalchemy import text
            c.execute(text(
                "INSERT INTO offer_evidence(offer_id, raw_message_id, source, seen_start_at) "
                "VALUES (:o,:r,:s,:d) ON CONFLICT (offer_id, raw_message_id) DO NOTHING"
            ), {"o": offer_id, "r": raw_message_id, "s": source, "d": seen_start})
    except Exception:  # noqa: BLE001, S110
        pass


def _recompute_offer(engine, offer_id):
    with engine.connect() as c:
        from sqlalchemy import text
        rows = c.execute(text("SELECT source, seen_start_at FROM offer_evidence WHERE offer_id=:o"), {"o": offer_id}).fetchall()
    evids = []
    for r in rows:
        src = r[0] if not hasattr(r, "source") else r.source
        sd = r[1] if not hasattr(r, "seen_start_at") else r.seen_start_at
        if isinstance(sd, str):
            sd = date.fromisoformat(sd)
        evids.append(Evidence(source=src, start_at=sd))
    if not evids:
        return
    cons = consolidate(evids)
    with engine.begin() as c:
        from sqlalchemy import text
        c.execute(text(
            "UPDATE offer SET start_at=:s, n_sources=:n, validated=:v, date_conflict=:dc, weight=:w WHERE id=:o"
        ), {"s": cons.start_at, "n": cons.n_sources, "v": cons.validated,
            "dc": cons.date_conflict, "w": cons.weight, "o": offer_id})


def collect_rss(engine=None, source=None, url=None, transport=None, robots_txt=None, now=None,
                min_interval=RATE_LIMIT_SEC, **kwargs):
    engine = engine if engine is not None else _engine_from(kwargs)
    source = source if source is not None else kwargs.get("source")
    url = url if url is not None else kwargs.get("url") or kwargs.get("feed_url")
    ts = _now(kwargs) if now is None else now
    rl = RateLimitState(min_interval=min_interval)
    raw_ids = []
    body = fetch_url(url, transport=transport, rate_limiter=rl, robots_txt=robots_txt)
    if body is None:
        return raw_ids
    if not isinstance(body, str):
        body = str(body)
    items = parse_feed(body)
    for it in items:
        content = it.get("title") or ""
        if SOURCES.get(source, {}).get("collect_body", True) and it.get("description"):
            content = (it.get("title") or "") + "\n" + (it.get("description") or "")
        if source and "pontospravoar" in source:
            content = it.get("title") or ""
        link = it.get("link")
        raw = store_raw(engine=engine, source=source, url=link or url, content=content or (it.get("title") or ""), collected_at=ts)
        raw_ids.append(raw.id if hasattr(raw, "id") else raw)
        try:
            process_raw_message(engine, raw, first_seen_at=ts)
        except Exception:  # noqa: BLE001, S110
            pass
    try:
        update_source_health(engine, source, items_new=len(raw_ids), extraction_rate=1.0 if raw_ids else 0.0,
                           robots_txt=robots_txt, now=ts)
    except Exception:  # noqa: BLE001, S110
        pass
    return raw_ids


def backfill(engine=None, source=None, from_=None, transport=None, robots_txt=None, **kwargs):
    engine = engine if engine is not None else _engine_from(kwargs)
    source = source if source is not None else kwargs.get("source")
    from_ = from_ if from_ is not None else kwargs.get("from") or kwargs.get("from_ts") or "202301"
    client = CDXClient(user_agent=UA)
    url_root = source if str(source).startswith("http") else f"http://{source}/"
    captures = []
    try:
        captures = client.list_captures(url_root, from_=from_, matchType="prefix",
                                       filter=["statuscode:200"], collapse=None)
    except Exception:  # noqa: BLE001
        captures = []
    stored = 0
    for cap in captures:
        if source and "pontospravoar" in source:
            continue
        try:
            url = cap.get("original") if hasattr(cap, "get") else cap["original"]
            ts = cap.get("timestamp") if hasattr(cap, "get") else cap["timestamp"]
            content = None
            if transport is not None:
                content = fetch_snapshot(ts, url, transport=transport)
            if not content:
                continue
            raw = store_raw(engine=engine, source=source, url=url, content=content, collected_at=None)
            stored += 1
            try:
                process_raw_message(engine, raw, first_seen_at=None)
            except Exception:  # noqa: BLE001, S110
                pass
        except Exception:  # noqa: BLE001, S112
            continue
    try:
        update_source_health(engine, source, items_new=stored, extraction_rate=1.0 if stored else 0.0,
                           robots_txt=robots_txt, now=None)
    except Exception:  # noqa: BLE001, S110
        pass
    return stored


def fetch_snapshot(timestamp, original, transport=None):
    url = f"https://web.archive.org/web/{timestamp}id_/{original}"
    if transport is not None:
        try:
            if hasattr(transport, "fetch"):
                return transport.fetch(url)
            return transport(url)
        except Exception:  # noqa: BLE001
            try:
                import httpx
                c = httpx.Client(transport=transport, headers={"User-Agent": UA})
                r = c.get(url)
                return r.text if hasattr(r, "text") else str(r)
            except Exception:  # noqa: BLE001
                return None
    return None


def update_source_health(engine, source, items_new=0, extraction_rate=None, robots_txt=None, now=None, **kwargs):
    items_new = kwargs.get("items_new", items_new)
    now = now if now is not None else _now(kwargs)
    if robots_txt is None:
        robots_txt = kwargs.get("robots_txt")
    try:
        with engine.begin() as c:
            from sqlalchemy import text
            c.execute(text(
                "INSERT INTO source_health(source, checked_at, items_new, extraction_rate, alert) "
                "VALUES (:s, :t, :i, :e, :a)"
            ), {"s": source, "t": (now if not isinstance(now, str) else datetime.fromisoformat(now)),
                "i": items_new, "e": extraction_rate, "a": (items_new == 0)})
    except Exception:  # noqa: BLE001, S110
        pass


# aliases
collect = collect_rss
collect_feed = collect_rss
collect_source = collect_rss
collect_rss_feed = collect_rss
run_collection = collect_rss
process_raw = process_raw_message
process_message = process_raw_message
ingest_offer = process_raw_message
store_offer = process_raw_message
process = process_raw_message
collect_all = collect_rss


__all__ = [
    "RATE_LIMIT_SEC",
    "SOURCES",
    "UA",
    "backfill",
    "collect",
    "collect_rss",
    "fetch_snapshot",
    "fetch_url",
    "parse_feed",
    "process_raw_message",
    "robots_allowed",
    "update_source_health",
]
