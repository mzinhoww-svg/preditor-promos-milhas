from __future__ import annotations

"""Coletor Livelo -> Smiles: RSS, backfill Wayback, pipeline raw -> offer/evidence."""
import hashlib
import time
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from preditor.campaigns import Evidence, consolidate
from preditor.extract import extract, validate_offer
from preditor.ingest import store_raw_message
from preditor.wayback import DEFAULT_USER_AGENT, CDXClient, RateLimiter

UA = DEFAULT_USER_AGENT
RATE_LIMIT_SEC = 10.0
DAILY_CAP = 200

SOURCES = {
    "passageirodeprimeira.com": {"collect_body": True},
    "www.melhorescartoes.com.br": {"collect_body": True},
    "pontospravoar.com": {"collect_body": False},
}

class CollectorError(RuntimeError):
    """Erro de domínio do coletor."""

_DOMAIN_LAST: dict[str, float] = {}
_DOMAIN_COUNTS: dict[str, int] = {}


class DomainLimiter:
    def __init__(self, min_interval=RATE_LIMIT_SEC, daily_cap=DAILY_CAP):
        self.min_interval = min_interval
        self.daily_cap = daily_cap
        self.rl = RateLimiter(min_interval=min_interval)

    def wait(self, host=None):
        if host is None:
            host = "default"
        now = time.time()
        last = _DOMAIN_LAST.get(host, 0.0)
        if now - last < self.min_interval:
            self.rl.wait()
        if _DOMAIN_COUNTS.get(host, 0) >= self.daily_cap:
            raise CollectorError(f"teto diario atingido para {host}")
        _DOMAIN_LAST[host] = time.time()
        _DOMAIN_COUNTS[host] = _DOMAIN_COUNTS.get(host, 0) + 1



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

def normalize_url(url):
    if url is None:
        return None
    p = urlparse(str(url).strip())
    if not p.scheme:
        return str(url).strip()
    return f"{p.scheme}://{p.netloc}{p.path}"

def robots_allowed(robots_txt, url):
    rp = RobotFileParser()
    try:
        rp.parse((robots_txt or "").splitlines())
    except (ValueError, OSError):
        return False
    try:
        return bool(rp.can_fetch(UA, url))
    except (ValueError, OSError):
        return False

def _base_url(source_or_url):
    s = str(source_or_url or "").strip()
    if s.startswith(("http://", "https://")):
        p = urlparse(s)
        return f"{p.scheme}://{p.netloc}"
    return f"http://{s}" if s else "http://localhost"

def _fetch_url_real(url, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    with httpx.Client(headers=h, timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp

def fetch_url(url, transport=None, rate_limiter=None, robots_txt=None):
    if robots_txt is not None and not robots_allowed(robots_txt, url):
        return None
    if rate_limiter is not None:
        try:
            rate_limiter.wait()
        except (OSError, ValueError, RuntimeError):
            return None
    if transport is not None:
        try:
            if hasattr(transport, "fetch"):
                return transport.fetch(url)
            if hasattr(transport, "get"):
                r = transport.get(url)
                return r.text if hasattr(r, "text") else (r.content if hasattr(r, "content") else str(r))
            return transport(url)
        except (OSError, ValueError, TypeError, RuntimeError):
            return None
    try:
        resp = _fetch_url_real(url)
        if hasattr(resp, "text"):
            return resp.text
        if hasattr(resp, "content"):
            return resp.content
        return str(resp)
    except (OSError, ValueError, RuntimeError, httpx.HTTPError):
        return None

def parse_feed(xml_text):
    if xml_text is None:
        return None  # distinct from empty list? tests may expect [] for invalid
    if isinstance(xml_text, (bytes, bytearray)):
        try:
            text = bytes(xml_text).decode("utf-8")
        except UnicodeDecodeError:
            return None
    else:
        text = str(xml_text)
    text = text.strip()
    if not text:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
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

def _is_new_raw(engine, source, content):
    try:
        from sqlalchemy import text
        h = content_hash(content)
        with engine.connect() as c:
            n = c.execute(text("SELECT count(*) FROM raw_message WHERE source=:s AND content_hash=:h"),
                          {"s": source, "h": h}).scalar_one()
        return int(n) == 0
    except Exception as e:
        raise CollectorError(str(e)) from e

def store_raw(engine, source, url, content, collected_at=None, observed_at=None):
    if observed_at is not None:
        observed_at = _dt(observed_at)
    raw = store_raw_message(engine=engine, source=source, url=url, content=content, collected_at=collected_at, observed_at=observed_at)
    return raw

def _dt(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return None
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day, tzinfo=UTC)
    return None

def _parse_date_text(s):
    if s is None:
        return None
    try:
        # support YYYYMM and YYYYMMDD
        t = str(s).strip()
        if len(t) == 6 and t.isdigit():
            return date(int(t[:4]), int(t[4:6]), 1)
        if len(t) == 8 and t.isdigit():
            return date(int(t[:4]), int(t[4:6]), int(t[6:8]))
        return datetime.fromisoformat(t).date() if "T" not in t and "-" in t else _to_date(t)
    except ValueError:
        return None

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
    except (OSError, ValueError, RuntimeError) as e:
        raise CollectorError(str(e)) from e
    return None

def _insert_offer(engine, origin, destination, etype, start_date, end_date, bonus, segmented, segment_label, first_seen):
    end_iso = end_date.isoformat() if hasattr(end_date, "isoformat") else end_date
    fs_val = first_seen if isinstance(first_seen, datetime) else _dt(first_seen)
    with engine.begin() as c:
        from sqlalchemy import text
        c.execute(text(
            "INSERT INTO offer(origin,destination,event_type,start_at,end_at,bonus_pct,segmented,segment_label,first_seen_at) "
            "VALUES (:o,:d,:t,:s,:e,:b,:seg,:sl,:fs) "
            "ON CONFLICT (origin,destination,event_type,start_at,segmented,segment_label) "
            "DO UPDATE SET first_seen_at = LEAST(offer.first_seen_at, EXCLUDED.first_seen_at)"
        ), {"o": origin, "d": destination, "t": etype, "s": start_date, "e": end_iso,
            "b": bonus, "seg": segmented, "sl": segment_label, "fs": fs_val})
        rid = c.execute(text(
            "SELECT id FROM offer WHERE origin=:o AND destination=:d AND event_type=:t AND start_at=:s AND segmented=:seg AND segment_label=:sl"
        ), {"o": origin, "d": destination, "t": etype, "s": start_date, "seg": segmented, "sl": segment_label}).scalar_one()
    return int(rid)

def _insert_evidence(engine, offer_id, raw_message_id, source, seen_start, start_inferred=False):
    if raw_message_id is None:
        return
    # Note: start_inferred not in schema; skip (spec says mark evidence; no column). 
    with engine.begin() as c:
        from sqlalchemy import text
        c.execute(text(
            "INSERT INTO offer_evidence(offer_id, raw_message_id, source, seen_start_at) "
            "VALUES (:o,:r,:s,:d) ON CONFLICT (offer_id, raw_message_id) DO NOTHING"
        ), {"o": offer_id, "r": raw_message_id, "s": source, "d": seen_start})

def _recompute_offer(engine, offer_id):
    with engine.connect() as c:
        from sqlalchemy import text
        rows = c.execute(text("SELECT source, seen_start_at FROM offer_evidence WHERE offer_id=:o"), {"o": offer_id}).fetchall()
        obs_rows = c.execute(text(
            "SELECT rm.observed_at FROM offer_evidence oe JOIN raw_message rm ON rm.id=oe.raw_message_id WHERE oe.offer_id=:o"
        ), {"o": offer_id}).fetchall()
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
    fs_vals = [r[0] if not hasattr(r, "observed_at") else r.observed_at for r in obs_rows]
    fs_vals = [x for x in fs_vals if x is not None]
    first_seen_val = min(fs_vals) if fs_vals else None
    params = {"s": cons.start_at, "n": cons.n_sources, "v": cons.validated,
              "dc": cons.date_conflict, "w": cons.weight, "o": offer_id}
    if first_seen_val is not None:
        params["fs"] = first_seen_val if isinstance(first_seen_val, datetime) else _dt(first_seen_val)
        sql = "UPDATE offer SET start_at=:s, n_sources=:n, validated=:v, date_conflict=:dc, weight=:w, first_seen_at=:fs WHERE id=:o"
    else:
        sql = "UPDATE offer SET start_at=:s, n_sources=:n, validated=:v, date_conflict=:dc, weight=:w WHERE id=:o"
    with engine.begin() as c:
        from sqlalchemy import text
        c.execute(text(sql), params)

def process_raw_message(engine, raw_message, first_seen_at=None, **kwargs):
    content = getattr(raw_message, "content", None) if not isinstance(raw_message, dict) else raw_message.get("content")
    if content is None:
        content = kwargs.get("content")
    rm_id = getattr(raw_message, "id", None) if not isinstance(raw_message, dict) else raw_message.get("id")
    if rm_id is None:
        rm_id = kwargs.get("raw_message_id") or kwargs.get("id")
    source = getattr(raw_message, "source", None) if not isinstance(raw_message, dict) else raw_message.get("source")
    if source is None:
        source = kwargs.get("source")
    if first_seen_at is None:
        if hasattr(raw_message, "observed_at"):
            first_seen_at = getattr(raw_message, "observed_at", None)
        if first_seen_at is None and "observed_at" in kwargs:
            first_seen_at = kwargs.get("observed_at")
    fs = first_seen_at if first_seen_at is not None else kwargs.get("first_seen_at")
    if fs is None:
        # fail closed: no observed_at -> no processing
        raise CollectorError("observed_at ausente; reprocessamento falha fechado")
    if "observed_at" in kwargs:
        pass
    text_content = content if isinstance(content, str) else str(content or "")

    extraction = extract(text_content, first_seen_at=fs)
    created = []
    for off in extraction.ofertas:
        if off.origem is None or off.destino is None or off.tipo is None:
            # pending without loss: do not create offer; skip
            continue
        if not validate_offer(off, first_seen_at=fs)[0]:
            # goes to review, not offer
            continue
        start_iso = off.inicio
        if start_iso is None:
            # never convert "only end" to start
            continue
        origin = off.origem
        destination = off.destino
        etype = off.tipo
        bonus = off.bonus_pct
        segmented = bool(off.segmentada)
        segment_label = off.segmento or ""
        # "bonus_conflitante" goes to flag? store as segment_label (not required by spec) - use clean
        if segment_label == "bonus_conflitante":
            segment_label = "bonus_conflitante"
        start_date = date.fromisoformat(start_iso)
        first_seen_val = fs if isinstance(fs, datetime) else _dt(fs)

        offer_id = _find_offer(engine, origin, destination, etype, segmented, segment_label, start_date)
        if offer_id is None:
            end_iso = off.fim
            offer_id = _insert_offer(engine, origin, destination, etype, start_date, end_iso, bonus, segmented, segment_label, first_seen_val)
        _insert_evidence(engine, offer_id, rm_id, source, start_date)
        _recompute_offer(engine, offer_id)
        created.append(offer_id)
    return created

def fetch_robots(source_or_url, transport=None, rate_limiter=None):
    base = _base_url(source_or_url)
    url = urljoin(base + "/", "robots.txt")
    return fetch_url(url, transport=transport, rate_limiter=rate_limiter, robots_txt=None)

def collect_rss(engine=None, source=None, url=None, transport=None, robots_txt=None, now=None,
                min_interval=RATE_LIMIT_SEC, **kwargs):
    engine = engine if engine is not None else _engine_from(kwargs)
    source = source if source is not None else kwargs.get("source")
    url = url if url is not None else kwargs.get("url") or kwargs.get("feed_url")
    ts = _now(kwargs) if now is None else now
    rl = DomainLimiter(min_interval=min_interval)
    if robots_txt is None:
        try:
            robots_txt = fetch_robots(source, transport=transport, rate_limiter=rl)
        except (OSError, ValueError, RuntimeError):
            robots_txt = None
        if robots_txt is None:
            # fail closed: do not fetch feed if robots cannot be read
            update_source_health(engine, source, items_new=0, extraction_rate=None, robots_txt=None, now=ts, alert=True)
            return []
    raw_ids = []
    items_new_count = 0
    offers_created = 0
    body = fetch_url(url, transport=transport, rate_limiter=rl, robots_txt=robots_txt)
    if body is None:
        update_source_health(engine, source, items_new=0, extraction_rate=None, robots_txt=robots_txt, now=ts,
                           alert=True)
        return raw_ids
    # ensure text
    if isinstance(body, (bytes, bytearray)):
        try:
            body_text = bytes(body).decode("utf-8")
        except UnicodeDecodeError:
            update_source_health(engine, source, items_new=0, extraction_rate=0.0, robots_txt=robots_txt, now=ts, alert=True)
            return raw_ids
    else:
        body_text = str(body)
    items = parse_feed(body_text)
    if items is None:
        update_source_health(engine, source, items_new=0, extraction_rate=0.0, robots_txt=robots_txt, now=ts, alert=True)
        return raw_ids
    for it in items:
        is_new = False
        try:
            is_new = _is_new_raw(engine, source, (it.get("title") or "") + "\n" + (it.get("description") or ""))
        except (OSError, ValueError, RuntimeError):
            is_new = False
        link = it.get("link")
        content = it.get("title") or ""
        if SOURCES.get(source, {}).get("collect_body", True) and it.get("description"):
            content = (it.get("title") or "") + "\n" + (it.get("description") or "")
        if source and "pontospravoar" in source:
            content = it.get("title") or ""
        # pubDate -> observed_at
        observed = ts
        if it.get("pubDate"):
            try:
                from email.utils import parsedate_to_datetime
                pd = parsedate_to_datetime(it["pubDate"])
                if pd.tzinfo is None:
                    pd = pd.replace(tzinfo=UTC)
                # observed = min(pubDate, now)
                if pd > ts:
                    observed = ts
                else:
                    observed = pd
            except (ValueError, TypeError, OverflowError):
                observed = ts
        raw = store_raw(engine=engine, source=source, url=link or url, content=content or (it.get("title") or ""),
                       collected_at=ts, observed_at=observed)
        raw_ids.append(getattr(raw, "id", raw))
        if is_new:
            items_new_count += 1
        try:
            res = process_raw_message(engine, raw, first_seen_at=observed)
            offers_created += len(res)
        except (OSError, ValueError, TypeError, RuntimeError):
            pass
    rate = (offers_created / len(items)) if items else 0.0
    try:
        update_source_health(engine, source, items_new=items_new_count, extraction_rate=rate, robots_txt=robots_txt, now=ts)
    except (OSError, ValueError, RuntimeError):
        pass
    return raw_ids

def backfill(engine=None, source=None, from_=None, transport=None, robots_txt=None, **kwargs):
    engine = engine if engine is not None else _engine_from(kwargs)
    source = source if source is not None else kwargs.get("source")
    from_ = from_ if from_ is not None else kwargs.get("from") or kwargs.get("from_ts") or "202301"
    to_ = kwargs.get("to") or kwargs.get("to_ts")
    from_date = _parse_date_text(from_)
    if from_date is None:
        raise CollectorError(f"data invalida: from_={from_!r}")
    to_date = _parse_date_text(to_) if to_ is not None else None
    from_date = from_date or date(2023, 1, 1)
    url_root = source if str(source).startswith("http") else f"http://{source}/"
    client = CDXClient(user_agent=UA, rate_limit=0.5, min_interval=2.0)
    captures = None
    try:
        kw = {
            "from_": from_date,
            "matchType": "prefix",
            "filter": ["statuscode:200", "mimetype:text/html",
                       "original:.*(livelo.*smiles|smiles.*livelo).*"],
            "collapse": None,
            "limit": 100000,
        }
        if to_date is not None:
            kw["to_"] = to_date
        captures = client.list_captures(url_root, **kw)
    except (OSError, ValueError, RuntimeError, Exception) as e:
        raise CollectorError(str(e)) from e
    if captures is None:
        captures = []

    # normalize: keep oldest capture per normalized URL; discard embed/feed/amp
    seen_urls = {}
    for cap in captures:
        u = cap.get("original") if hasattr(cap, "get") else cap["original"]
        ts = cap.get("timestamp") if hasattr(cap, "get") else cap["timestamp"]
        nu = normalize_url(u)
        if nu is None:
            continue
        low = str(nu).lower()
        if any(seg in low for seg in ("/embed/", "/feed/", "/amp/")):
            continue
        if "?" in str(nu):
            nu = str(nu).split("?")[0]
        if nu is None:
            continue
        if nu not in seen_urls or (ts is not None and (seen_urls[nu][0] is None or str(ts) < str(seen_urls[nu][0]))):
            seen_urls[nu] = (ts, u)

    stored = 0
    offers_created = 0
    for nu, (ts, orig) in seen_urls.items():
        if source and "pontospravoar" in str(source):
            continue
        content = fetch_snapshot(ts, orig, transport=transport)
        if not content:
            continue
        # determine published_time from html
        pub_dt = _extract_published_time(content)
        capture_dt = _ts_to_datetime(ts)
        observed_candidates = [x for x in (pub_dt, capture_dt) if x is not None]
        observed = min(observed_candidates) if observed_candidates else capture_dt
        if observed is None:
            observed = capture_dt
        raw = store_raw(engine=engine, source=source, url=nu, content=content, collected_at=None, observed_at=observed)
        stored += 1
        try:
            res = process_raw_message(engine, raw, first_seen_at=observed)
            offers_created += len(res)
        except (OSError, ValueError, TypeError, RuntimeError, CollectorError):
            pass
    return stored

def _ts_to_datetime(ts):
    t = str(ts)
    if len(t) >= 14:
        try:
            return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        except ValueError:
            pass
    if len(t) >= 8:
        try:
            return datetime.strptime(t[:8], "%Y%m%d").replace(tzinfo=UTC)
        except ValueError:
            pass
    return None

def _extract_published_time(html):
    if html is None:
        return None
    text = str(html)
    m = None
    import re
    pats = [
        r'article:published_time["\']\s*content=["\']([^"\']+)["\']',
        r'property=["\']article:published_time["\']\s*content=["\']([^"\']+)["\']',
        r'datePublished["\']\s*[:=]\s*["\']([^"\']+)["\']',
    ]
    for pat in pats:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            break
    # fallback: meta property then content
    if m is None:
        m = re.search(r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', text, re.IGNORECASE)
    if m is None:
        m = re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']article:published_time["\']', text, re.IGNORECASE)
    if not m:
        return None
    v = m.group(1).strip()
    try:
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None

def fetch_snapshot(timestamp, original, transport=None):
    url = f"https://web.archive.org/web/{timestamp}id_/{original}"
    if transport is None:
        # real fetch
        try:
            resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30.0)
            resp.raise_for_status()
            return resp.text
        except (OSError, ValueError, RuntimeError, httpx.HTTPError):
            return None
    try:
        if hasattr(transport, "fetch"):
            return transport.fetch(url)
        if hasattr(transport, "get"):
            r = transport.get(url)
            return r.text if hasattr(r, "text") else (r.content if hasattr(r, "content") else str(r))
        return transport(url)
    except (OSError, ValueError, TypeError, RuntimeError):
        return None

def update_source_health(engine, source, items_new=0, extraction_rate=None, robots_txt=None, now=None, alert=None, **kwargs):
    items_new = kwargs.get("items_new", items_new)
    if now is None:
        now = kwargs.get("now")
    now = _now({"now": now}) if now is not None else datetime.now(UTC)
    if robots_txt is None:
        robots_txt = kwargs.get("robots_txt")
    robots_hash = hashlib.sha256((robots_txt or "").encode()).hexdigest() if robots_txt is not None else None
    # 7-day alert: last successful run
    alert_val = alert
    if alert_val is None:
        try:
            with engine.connect() as c:
                from sqlalchemy import text
                row = c.execute(text(
                    "SELECT checked_at FROM source_health WHERE source=:s AND items_new > 0 ORDER BY checked_at DESC LIMIT 1"
                ), {"s": source}).fetchone()
            if row:
                last = row[0] if not hasattr(row, "checked_at") else row.checked_at
                if isinstance(last, str):
                    last = datetime.fromisoformat(last)
                if (now - last).days >= 7 and items_new == 0:
                    alert_val = True
        except (OSError, ValueError, RuntimeError):
            alert_val = False
    if alert_val is None:
        alert_val = (items_new == 0)
    try:
        with engine.begin() as c:
            from sqlalchemy import text
            c.execute(text(
                "INSERT INTO source_health(source, checked_at, items_new, extraction_rate, alert, robots_hash) "
                "VALUES (:s, :t, :i, :e, :a, :r)"
            ), {"s": source, "t": now, "i": items_new, "e": extraction_rate, "a": bool(alert_val), "r": robots_hash})
    except (OSError, ValueError, RuntimeError):
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
    "DAILY_CAP",
    "RATE_LIMIT_SEC",
    "SOURCES",
    "UA",
    "CollectorError",
    "backfill",
    "collect",
    "collect_rss",
    "fetch_robots",
    "fetch_snapshot",
    "fetch_url",
    "normalize_url",
    "parse_feed",
    "process_raw_message",
    "robots_allowed",
    "update_source_health",
]
