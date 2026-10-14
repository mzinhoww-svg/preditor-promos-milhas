"""Backfill real Livelo -> Smiles via Wayback (resumavel, rate-limited)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

try:
    from preditor import collector as C
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from preditor import collector as C

STATE_PATH = Path("data/raw/backfill/state.json")
RATE_LIMIT_DEFAULT = 10.0
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


def fetch_cdx_candidates(source: str, from_date: date, to_date: date | None, rate_limit: float, page_size: int) -> list[dict]:
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
    kw0 = {
        "from_": from_date,
        "matchType": "prefix",
        "filter": ["statuscode:200", "mimetype:text/html", "original:.*(livelo.*smiles|smiles.*livelo).*"],
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


def run_backfill(args: argparse.Namespace) -> dict:
    state = _load_state()
    state.setdefault("version", 1)
    state.setdefault("params", {})
    state["params"].update({
        "from_": args.from_,
        "to": args.to,
        "rate_limit": args.rate_limit,
        "sources": args.sources,
    })
    state.setdefault("sources", {})
    engine = None
    if args.database_url:
        import sqlalchemy

        engine = sqlalchemy.create_engine(args.database_url)
    from_date = C._parse_date_text(args.from_)
    if from_date is None:
        raise SystemExit(f"data invalida: from_={args.from_!r}")
    to_date = C._parse_date_text(args.to) if args.to is not None else None
    from datetime import date as _date

    if from_date is None:
        from_date = _date(2023, 1, 1)

    summary: dict[str, dict] = {}
    for source in args.sources:
        src_state = state["sources"].setdefault(source, {})
        src_state.setdefault("processed", {})
        processed = src_state["processed"]
        # robots
        robots_txt = None
        try:
            robots_txt = C.fetch_robots(source, transport=None, rate_limiter=None)
        except (OSError, ValueError, RuntimeError, TypeError):
            robots_txt = None
        src_state["robots_hash"] = _robots_hash(robots_txt)
        # verify root permission (fail closed only when robots explicitly parsed)
        if robots_txt is not None and not C.robots_allowed(robots_txt, (f"http://{source}/" if not str(source).startswith("http") else source)):
            raise SystemExit(f"robots.txt bloqueia a fonte {source}")

        # candidates
        candidates = src_state.get("cdx_candidates")
        if not candidates or args.refresh_candidates:
            candidates = fetch_cdx_candidates(source, from_date, to_date, args.rate_limit, args.page_size)
            src_state["cdx_candidates"] = candidates
            # count-only sources do not download body (decision 002)
            src_state["cdx_unique_urls"] = len(candidates)
            src_state["cdx_months"] = len({(c.get("timestamp") or "")[:6] for c in candidates})
            _save_state(state)

        download_body = not (args.titles_only or "pontospravoar" in str(source).lower())
        stored_this_run = 0
        offers_this_run = 0
        for cand in candidates:
            url = cand["url"]
            ts = cand["timestamp"]
            if url in processed and processed[url].get("status") == "done":
                continue
            if not download_body:
                processed[url] = {"status": "listed_only", "timestamp": ts}
                _save_state(state)
                continue
            time.sleep(args.rate_limit)
            content = C.fetch_snapshot(ts, url, transport=None)
            if not content:
                processed[url] = {"status": "fetch_failed", "timestamp": ts}
                _save_state(state)
                continue
            pub_dt = C._extract_published_time(content)
            capture_dt = C._ts_to_datetime(ts)
            observed_candidates = [x for x in (pub_dt, capture_dt) if x is not None]
            observed = min(observed_candidates) if observed_candidates else capture_dt
            if observed is None:
                observed = capture_dt
            try:
                if engine is not None:
                    eng = engine
                else:
                    # lazy connect from env
                    import os

                    import sqlalchemy

                    u = os.environ.get("DATABASE_URL")
                    if not u:
                        raise SystemExit("DATABASE_URL ausente")
                    eng = sqlalchemy.create_engine(u)
                raw = C.store_raw(engine=eng, source=source, url=url, content=content, collected_at=None, observed_at=observed)
                raw_id = getattr(raw, "id", None)
                res = C.process_raw_message(eng, raw, first_seen_at=observed)
                offers_this_run += len(res)
                stored_this_run += 1
                processed[url] = {"status": "done", "timestamp": ts, "raw_id": raw_id, "offers": len(res)}
            except (OSError, ValueError, RuntimeError, TypeError) as exc:
                processed[url] = {"status": "error", "timestamp": ts, "error": str(exc)}
            _save_state(state)

        summary[source] = {
            "candidates": len(candidates),
            "months": src_state.get("cdx_months"),
            "stored_this_run": stored_this_run,
            "offers_this_run": offers_this_run,
            "processed_done": sum(1 for v in processed.values() if v.get("status") == "done"),
        }
        _save_state(state)

    state["last_run"] = _now()
    state["summary"] = summary
    _save_state(state)
    return {"state_path": str(STATE_PATH), "summary": summary}


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
    parser.add_argument("--titles-only", dest="titles_only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.sources:
        args.sources = list(SOURCES_DEFAULT)
    if isinstance(args.sources, str):
        args.sources = [args.sources]
    result = run_backfill(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
