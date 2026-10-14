"""Backfill real Livelo -> Smiles via Wayback (resumavel, rate-limited)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

try:
    from preditor import article as A
    from preditor import collector as C
    from preditor.stop import StopRequested, check_stop
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from preditor import article as A
    from preditor import collector as C
    from preditor.stop import StopRequested, check_stop

STATE_PATH = Path("data/raw/backfill/state.json")
RATE_LIMIT_DEFAULT = 10.0
GAP_DAYS = 7
BACKOFF_BASE = 30.0
BACKOFF_TRIES = 3
SOURCES_DEFAULT = ["passageirodeprimeira.com", "www.melhorescartoes.com.br", "pontospravoar.com"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (OSError, ValueError):
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str))
    tmp.replace(STATE_PATH)


def _robots_hash(text_value: str | None) -> str | None:
    if text_value is None:
        return None
    return hashlib.sha256(text_value.encode("utf-8", "replace")).hexdigest()


def _normalize_candidate(cap: dict) -> tuple[str | None, str | None]:
    u = cap.get("original")
    ts = cap.get("timestamp")
    nu = C.normalize_url(u)
    if nu is None:
        return None, None
    surl = str(nu).replace("%0A", "").replace("%0a", "")
    low = surl.lower()
    if any(seg in low for seg in ("/embed/", "/feed/", "/amp/")):
        return None, None
    if "?" in surl:
        surl = surl.split("?")[0]
    if "%0a" in surl.lower():
        surl = surl.replace("%0A", "").replace("%0a", "")
    return surl, ts


def _new_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": C.UA}, timeout=30.0, follow_redirects=True)


def fetch_robots_strict(source: str) -> tuple[str, str | None]:
    """robots.txt fail-closed: segue redirects; so 200 (texto) ou 404/410 (sem restricoes) liberam."""
    host = source if not str(source).startswith("http") else str(source).split("//", 1)[1].split("/", 1)[0]
    last: tuple[str, str | None] = ("robots_unavailable", None)
    for scheme in ("https", "http"):
        try:
            with _new_client() as client:
                resp = client.get(f"{scheme}://{host}/robots.txt")
        except (httpx.HTTPError, OSError, ValueError):
            continue
        if resp.status_code == 200:
            return "ok", resp.text
        if resp.status_code in (404, 410):
            return "ok", ""
        last = ("robots_unavailable", None)
    return last


def fetch_snapshot_backoff(timestamp: str, original: str) -> str | None:
    """HTML original da Wayback; backoff exponencial em 429/503."""
    url = f"https://web.archive.org/web/{timestamp}id_/{original}"
    delay = BACKOFF_BASE
    for attempt in range(BACKOFF_TRIES):
        try:
            with _new_client() as client:
                resp = client.get(url)
        except (httpx.HTTPError, OSError, ValueError):
            return None
        if resp.status_code == 200:
            return resp.text
        if resp.status_code in (429, 503) and attempt < BACKOFF_TRIES - 1:
            time.sleep(delay)
            delay *= 2
            continue
        return None
    return None


def _observed(pub_dt: datetime | None, capture_dt: datetime | None) -> datetime | None:
    cands = [x for x in (pub_dt, capture_dt) if x is not None]
    return min(cands) if cands else None


def _mark_gap(engine, raw_id, published_at, gap: bool) -> None:
    import sqlalchemy

    with engine.begin() as c:
        c.execute(sqlalchemy.text(
            "UPDATE raw_message SET published_at=:p, published_vs_capture_gap=:g WHERE id=:i"
        ), {"p": published_at, "g": gap, "i": raw_id})


def _process_snippets(engine, source, raw_id, content, observed) -> int:
    n = 0
    for snip in A.snippets(A.article_text(content)):
        res = C.process_raw_message(engine, {"content": snip, "id": raw_id, "source": source}, first_seen_at=observed)
        n += len(res)
    return n


def ingest_page(engine, source: str, url: str, ts: str, content: str) -> dict:
    pub_dt = C._extract_published_time(content)
    capture_dt = C._ts_to_datetime(ts)
    observed = _observed(pub_dt, capture_dt)
    if observed is None:
        return {"status": "skipped_no_date"}  # falha fechada: sem data nao grava
    gap = bool(pub_dt is not None and capture_dt is not None and capture_dt - pub_dt > timedelta(days=GAP_DAYS))
    raw = C.store_raw(engine=engine, source=source, url=url, content=content, collected_at=None, observed_at=observed)
    raw_id = getattr(raw, "id", None)
    _mark_gap(engine, raw_id, pub_dt, gap)
    n = _process_snippets(engine, source, raw_id, content, observed)
    return {"status": "done", "raw_id": raw_id, "offers": n, "gap": gap}


def fetch_cdx_candidates(source: str, from_date: date, to_date: date | None, rate_limit: float, page_size: int,
                         slug_mode: str = "either") -> list[dict]:
    url_root = source if str(source).startswith("http") else f"http://{source}/"
    client = C.CDXClient(
        user_agent=C.UA,
        rate_limit=1.0 / rate_limit if rate_limit > 0 else 0.0,
        min_interval=rate_limit,
        timeout=120.0,
        max_retries=3,
    )
    captures: list[dict] = []
    seen_resume: set[str] = set()
    slug_re = "(livelo|smiles)" if slug_mode == "either" else "(livelo.*smiles|smiles.*livelo)"
    kw0 = {
        "from_": from_date,
        "matchType": "prefix",
        "filter": ["statuscode:200", "mimetype:text/html", f"original:.*{slug_re}.*"],
        "collapse": None,
        "limit": page_size,
        "showResumeKey": True,
    }
    if to_date is not None:
        kw0["to_"] = to_date
    resume = None
    pages = 0
    while pages < 10000:
        kw = dict(kw0)
        if resume:
            if resume in seen_resume:
                break
            seen_resume.add(resume)
            kw["resumeKey"] = resume
        page = client.list_captures(url_root, **kw)
        if not page:
            break
        captures.extend(page)
        resume = getattr(client, "last_resume_key", None)
        pages += 1
        print(f"[cdx] {source} pagina {pages}: +{len(page)} capturas (total {len(captures)})", file=sys.stderr, flush=True)
        if not resume:
            break
        time.sleep(rate_limit)
    # normalize unique oldest
    seen_urls: dict[str, str] = {}
    for cap in captures:
        nu, ts = _normalize_candidate(cap)
        if nu is None:
            continue
        if nu not in seen_urls or (ts is not None and (seen_urls[nu] is None or str(ts) < str(seen_urls[nu]))):
            seen_urls[nu] = ts
    return [{"url": nu, "timestamp": ts} for nu, ts in sorted(seen_urls.items())]


def _engine(args):
    import os

    import sqlalchemy

    url = args.database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL ausente")
    return sqlalchemy.create_engine(url)


def slug_priority(url: str) -> int:
    """Prioridade de busca pelo slug: os dois programas e transferencia pesam mais."""
    low = url.lower()
    has_l, has_s = "livelo" in low, "smiles" in low
    if not (has_l or has_s):
        return 0
    score = 1 + (3 if has_l and has_s else 0)
    if re.search(r"transfer", low):
        score += 2
    if re.search(r"b[oô]nus|bonific", low):
        score += 1
    return score


def _retry_allowed(prev: dict, max_attempts: int) -> bool:
    if prev.get("status") in (None, "listed_only"):
        return True
    if prev.get("status") in ("done", "robots_disallowed", "skipped_no_date"):
        return False
    return prev.get("attempts", 1) < max_attempts


def run_backfill(args: argparse.Namespace) -> dict:
    check_stop()
    state = _load_state()
    state.setdefault("version", 2)
    state.setdefault("params", {})
    state["params"].update({
        "from_": args.from_, "to": args.to, "rate_limit": args.rate_limit, "sources": args.sources,
        "slug_mode": getattr(args, "slug_mode", "either"),
    })
    state.setdefault("sources", {})
    from_date = C._parse_date_text(args.from_)
    if from_date is None:
        raise SystemExit(f"data invalida: from_={args.from_!r}")
    to_date = C._parse_date_text(args.to) if args.to is not None else None
    max_attempts = getattr(args, "max_attempts", 3)
    slug_mode = getattr(args, "slug_mode", "either")
    engine = None

    summary: dict[str, dict] = {}
    for idx, source in enumerate(args.sources):
        check_stop()
        if idx > 0:
            time.sleep(max(args.rate_limit, 10.0))  # >=10 s entre fontes
        src_state = state["sources"].setdefault(source, {})
        src_state.setdefault("processed", {})
        processed = src_state["processed"]

        status, robots_txt = fetch_robots_strict(source)
        src_state["robots_status"] = status
        src_state["robots_hash"] = _robots_hash(robots_txt)
        if status != "ok":
            src_state["status"] = "robots_unavailable"
            summary[source] = {"status": "robots_unavailable", "candidates": 0, "processed_done": 0}
            _save_state(state)
            continue
        root = source if str(source).startswith("http") else f"http://{source}/"
        if not C.robots_allowed(robots_txt, root):
            src_state["status"] = "robots_disallowed"
            summary[source] = {"status": "robots_disallowed", "candidates": 0, "processed_done": 0}
            _save_state(state)
            continue
        src_state["status"] = "ok"

        candidates = src_state.get("cdx_candidates")
        if not candidates or args.refresh_candidates or src_state.get("slug_mode") != slug_mode:
            candidates = fetch_cdx_candidates(source, from_date, to_date, args.rate_limit, args.page_size, slug_mode)
            src_state["cdx_candidates"] = candidates
            src_state["slug_mode"] = slug_mode
            src_state["cdx_unique_urls"] = len(candidates)
            src_state["cdx_months"] = len({(c.get("timestamp") or "")[:6] for c in candidates})
            _save_state(state)

        download_body = not (args.titles_only or "pontospravoar" in str(source).lower())
        stored_this_run = 0
        offers_this_run = 0
        fetched_this_run = 0
        max_fetch = getattr(args, "max_fetch", None)
        ordered = sorted(candidates, key=lambda c: (-slug_priority(c["url"]), c["url"]))
        for cand in ordered:
            check_stop()
            url = cand["url"]
            ts = cand["timestamp"]
            prev = processed.get(url, {})
            if prev.get("status") == "done" or not _retry_allowed(prev, max_attempts):
                continue
            if not download_body:
                processed[url] = {"status": "listed_only", "timestamp": ts}
                continue
            if not C.robots_allowed(robots_txt, url):
                processed[url] = {"status": "robots_disallowed", "timestamp": ts}
                _save_state(state)
                continue
            if max_fetch is not None and fetched_this_run >= max_fetch:
                break
            fetched_this_run += 1
            attempts = prev.get("attempts", 0) + 1
            time.sleep(args.rate_limit)
            check_stop()
            content = fetch_snapshot_backoff(ts, url)
            check_stop()
            if not content:
                processed[url] = {"status": "fetch_failed", "timestamp": ts, "attempts": attempts}
                _save_state(state)
                continue
            try:
                if engine is None:
                    engine = _engine(args)
                res = ingest_page(engine, source, url, ts, content)
            except (OSError, ValueError, RuntimeError, TypeError) as exc:
                res = {"status": "error", "error": str(exc)}
            res.setdefault("timestamp", ts)
            res["attempts"] = attempts
            processed[url] = res
            if res.get("status") == "done":
                stored_this_run += 1
                offers_this_run += res.get("offers", 0)
            _save_state(state)

        from collections import Counter

        summary[source] = {
            "status": "ok",
            "candidates": len(candidates),
            "months": src_state.get("cdx_months"),
            "stored_this_run": stored_this_run,
            "offers_this_run": offers_this_run,
            "processed_done": sum(1 for v in processed.values() if v.get("status") == "done"),
            "by_status": dict(Counter(v.get("status") for v in processed.values())),
        }
        _save_state(state)

    state["last_run"] = _now()
    state["summary"] = summary
    _save_state(state)
    return {"state_path": str(STATE_PATH), "summary": summary}


def list_feed_captures(feed_url: str, from_date: date, rate_limit: float, page_size: int = 500) -> list[dict]:
    """Capturas arquivadas do feed (CDX, 1 por dia, so 200)."""
    client = C.CDXClient(user_agent=C.UA, rate_limit=1.0 / rate_limit if rate_limit > 0 else 0.0,
                         min_interval=rate_limit, timeout=120.0, max_retries=3)
    caps: list[dict] = []
    resume = None
    for _ in range(200):
        kw = {"from_": from_date, "matchType": "exact", "filter": ["statuscode:200"],
              "collapse": "timestamp:8", "limit": page_size, "showResumeKey": True}
        if resume:
            kw["resumeKey"] = resume
        page = client.list_captures(feed_url, **kw)
        if not page:
            break
        caps.extend(page)
        resume = getattr(client, "last_resume_key", None)
        if not resume:
            break
        time.sleep(rate_limit)
    return [{"timestamp": str(c.get("timestamp")), "original": c.get("original") or feed_url} for c in caps]


def _thin(caps: list[dict], step_days: int) -> list[dict]:
    out, last = [], None
    for c in sorted(caps, key=lambda x: x["timestamp"]):
        d = C._ts_to_datetime(c["timestamp"])
        if d is None:
            continue
        if last is None or (d - last).days >= step_days:
            out.append(c)
            last = d
    return out


def _pub_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    from email.utils import parsedate_to_datetime

    try:
        d = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def collect_archived_feed(engine, source: str, feed_url: str, from_date: date, rate_limit: float = 10.0,
                          step_days: int = 5) -> dict:
    """RSS arquivado (decisao 002, opcao C): so titulo, data e link de cada captura; nunca o corpo."""
    check_stop()
    status, robots_txt = fetch_robots_strict(source)
    if status != "ok":
        return {"status": "robots_unavailable", "captures": 0, "items": 0}
    if not C.robots_allowed(robots_txt, feed_url):
        return {"status": "robots_disallowed", "captures": 0, "items": 0}
    state = _load_state()
    fs = state.setdefault("feeds", {}).setdefault(feed_url, {"done": {}})
    done = fs["done"]
    caps = _thin(list_feed_captures(feed_url, from_date, rate_limit), step_days)
    items_total = 0
    for cap in caps:
        check_stop()
        ts = cap["timestamp"]
        if ts in done:
            continue
        time.sleep(rate_limit)
        xml = fetch_snapshot_backoff(ts, cap["original"])
        capture_dt = C._ts_to_datetime(ts)
        parsed = C.parse_feed(xml) if xml else None
        if parsed is None or capture_dt is None:
            done[ts] = {"status": "fetch_failed"}
            _save_state(state)
            continue
        n = 0
        for it in parsed:
            check_stop()
            title = (it.get("title") or "").strip()
            if not title:
                continue
            pub = _pub_date(it.get("pubDate"))
            observed = _observed(pub, capture_dt)
            raw = C.store_raw(engine=engine, source=source, url=it["link"], content=title,
                              collected_at=None, observed_at=observed)
            rid = getattr(raw, "id", None)
            gap = bool(pub is not None and capture_dt - pub > timedelta(days=GAP_DAYS))
            _mark_gap(engine, rid, pub, gap)
            C.process_raw_message(engine, {"content": title, "id": rid, "source": source}, first_seen_at=observed)
            n += 1
        items_total += n
        done[ts] = {"status": "done", "items": n}
        _save_state(state)
    return {"status": "ok", "captures": len(caps), "items": items_total}


def collect_titles_rss(engine, source: str, feed_url: str) -> dict:
    """2a fonte (decisao 002, opcao C): so titulo/data/link do RSS; robots fail-closed antes de buscar."""
    check_stop()
    status, robots_txt = fetch_robots_strict(source)
    if status != "ok":
        return {"status": "robots_unavailable", "items": 0}
    if not C.robots_allowed(robots_txt, feed_url):
        return {"status": "robots_disallowed", "items": 0}
    ids = C.collect_rss(engine=engine, source=source, url=feed_url, robots_txt=robots_txt)
    return {"status": "ok", "items": len(ids or [])}


def dedupe_extensions(engine) -> int:
    """Funde ofertas iguais (mesmo par, tipo, inicio e bonus) que so diferem no fim: prorrogacao."""
    import sqlalchemy as sa

    merged = 0
    with engine.begin() as c:
        groups = c.execute(sa.text(
            "SELECT array_agg(id ORDER BY first_seen_at, id) FROM offer "
            "GROUP BY origin, destination, event_type, start_at, bonus_pct HAVING count(*) > 1")).scalars().all()
        for ids in groups:
            keep, drop = ids[0], ids[1:]
            c.execute(sa.text("UPDATE offer SET end_at=(SELECT max(end_at) FROM offer WHERE id = ANY(:ids)) WHERE id=:k"),
                      {"ids": ids, "k": keep})
            c.execute(sa.text("UPDATE offer_evidence SET offer_id=:k WHERE offer_id = ANY(:d) AND NOT EXISTS ("
                              "SELECT 1 FROM offer_evidence e2 WHERE e2.offer_id=:k AND "
                              "e2.raw_message_id=offer_evidence.raw_message_id)"), {"k": keep, "d": drop})
            c.execute(sa.text("DELETE FROM offer_evidence WHERE offer_id = ANY(:d)"), {"d": drop})
            c.execute(sa.text("DELETE FROM offer WHERE id = ANY(:d)"), {"d": drop})
            merged += len(drop)
    if merged:
        with engine.connect() as c:
            ids = c.execute(sa.text("SELECT id FROM offer")).scalars().all()
        for oid in ids:
            C._recompute_offer(engine, oid)
    return merged


def recompute_gap(engine, ts_by_url: dict[str, str]) -> int:
    check_stop()
    """Marca published_vs_capture_gap nas mensagens ja gravadas (timestamp da captura vem do state)."""
    import sqlalchemy as sa

    with engine.connect() as c:
        rows = c.execute(sa.text(
            "SELECT id, url, content, published_at, published_vs_capture_gap FROM raw_message")).all()
    flagged = 0
    for rid, url, content, old_pub, old_gap in rows:
        pub = C._extract_published_time(content)
        cap = C._ts_to_datetime(ts_by_url.get(url)) if ts_by_url.get(url) else None
        if pub is None or cap is None:
            # sem HTML/captura nao ha como recalcular: preserva o que ja foi gravado (ex.: titulo de RSS)
            flagged += int(bool(old_gap))
            continue
        gap = cap - pub > timedelta(days=GAP_DAYS)
        _mark_gap(engine, rid, pub, gap)
        flagged += int(gap)
    return flagged


def reprocess(engine) -> dict:
    """Apaga ofertas/evidencias e reextrai de raw_message so do corpo do artigo (sem rede)."""
    import sqlalchemy as sa

    check_stop()  # antes do DELETE

    with engine.connect() as c:
        old = {tuple(str(x) for x in r) for r in c.execute(sa.text(
            "SELECT origin,destination,event_type,start_at,bonus_pct FROM offer")).all()}
    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM offer_evidence"))
        c.execute(sa.text("DELETE FROM offer"))
    with engine.connect() as c:
        rows = c.execute(sa.text(
            "SELECT id, source, content, observed_at FROM raw_message WHERE observed_at IS NOT NULL ORDER BY id")).all()
    for rid, source, content, observed in rows:
        check_stop()
        _process_snippets(engine, source, rid, content, observed)
    merged = dedupe_extensions(engine)
    with engine.connect() as c:
        new = {tuple(str(x) for x in r) for r in c.execute(sa.text(
            "SELECT origin,destination,event_type,start_at,bonus_pct FROM offer")).all()}
        n_new = c.execute(sa.text("SELECT count(*) FROM offer")).scalar_one()
    return {"raw_messages": len(rows), "old_offers": len(old), "new_offers": int(n_new),
            "merged_extensions": merged, "discarded_vs_old": len(old - new)}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill real Livelo->Smiles via Wayback (resumavel)")
    parser.add_argument("--source", dest="sources", action="append", help="fonte (repetivel)")
    parser.add_argument("--sources", nargs="*", help="lista de fontes")
    parser.add_argument("--from", dest="from_", default="202301")
    parser.add_argument("--to", dest="to", default=None)
    parser.add_argument("--rate-limit", dest="rate_limit", type=float, default=RATE_LIMIT_DEFAULT)
    parser.add_argument("--page-size", dest="page_size", type=int, default=500)
    parser.add_argument("--database-url", dest="database_url", default=None)
    parser.add_argument("--refresh-candidates", dest="refresh_candidates", action="store_true")
    parser.add_argument("--max-fetch", dest="max_fetch", type=int, default=None,
                        help="teto de downloads novos por fonte nesta execucao (por prioridade do slug)")
    parser.add_argument("--feed-step-days", dest="feed_step_days", type=int, default=5)
    parser.add_argument("--rss-archive", dest="rss_archive", default=None,
                        help="URL do feed; lista capturas pela CDX e le so titulo/data/link")
    parser.add_argument("--rss-titles", dest="rss_titles", default=None, help="URL do feed (so titulo/data/link)")
    parser.add_argument("--reprocess", action="store_true", help="reextrai de raw_message (sem rede)")
    parser.add_argument("--max-attempts", dest="max_attempts", type=int, default=3)
    parser.add_argument("--slug-mode", dest="slug_mode", choices=["either", "both"], default="either")
    parser.add_argument("--titles-only", dest="titles_only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        return _main(args)
    except StopRequested as exc:
        print(f"STOP: {exc}")
        return 3


def _main(args: argparse.Namespace) -> int:
    check_stop()
    if not args.sources:
        args.sources = list(SOURCES_DEFAULT)
    if isinstance(args.sources, str):
        args.sources = [args.sources]
    if args.rss_archive:
        src = args.sources[0]
        out = collect_archived_feed(_engine(args), src, args.rss_archive, C._parse_date_text(args.from_),
                                    rate_limit=args.rate_limit, step_days=args.feed_step_days)
        print(json.dumps(out, ensure_ascii=False))
        return 0
    if args.rss_titles:
        src = args.sources[0]
        print(json.dumps(collect_titles_rss(_engine(args), src, args.rss_titles), ensure_ascii=False))
        return 0
    if args.reprocess:
        eng = _engine(args)
        ts_by_url = {u: v.get("timestamp") for src in _load_state().get("sources", {}).values()
                     for u, v in src.get("processed", {}).items() if v.get("timestamp")}
        out = reprocess(eng)
        out["gap_flagged"] = recompute_gap(eng, ts_by_url)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    result = run_backfill(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
