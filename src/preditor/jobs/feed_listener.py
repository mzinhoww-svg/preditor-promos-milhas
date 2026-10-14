"""Listener recorrente de feeds (decisao 002): job idempotente que alimenta raw_message, extrai
ofertas e grava source_health por fonte.

- Pontos pra Voar: so titulo/data/link do RSS (nunca o corpo).
- Passageiro de Primeira e Melhores Cartoes: artigo integral, so de URLs que o robots.txt libera.
- 1 req/10 s por dominio, robots fail-closed (indisponivel => fonte pulada, alerta no source_health).
- Idempotente: item cuja URL ja esta em raw_message nao e buscado de novo.

Uso: `python -m preditor.jobs.feed_listener --once` (agendar por cron; ex.: a cada 30 min).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import sqlalchemy as sa

from preditor import collector as C

INTERVAL = 10.0
GAP_DAYS = 7

FEEDS: list[dict[str, str]] = [
    {"source": "pontospravoar.com", "feed": "https://pontospravoar.com/feed/", "mode": "titles"},
    {"source": "passageirodeprimeira.com", "feed": "https://passageirodeprimeira.com/feed/", "mode": "article"},
    {"source": "www.melhorescartoes.com.br", "feed": "https://www.melhorescartoes.com.br/feed", "mode": "article"},
]


def _http_get(url: str) -> tuple[int, str]:
    try:
        with httpx.Client(headers={"User-Agent": C.UA}, timeout=30.0, follow_redirects=True) as c:
            r = c.get(url)
        return r.status_code, r.text
    except (httpx.HTTPError, OSError, ValueError):
        return 0, ""


class _Pacer:
    """1 req/10 s por dominio: dorme o intervalo inteiro entre requisicoes ao mesmo dominio."""

    def __init__(self, sleep: Callable[[float], None], interval: float = INTERVAL):
        self.sleep, self.interval, self.seen = sleep, interval, set()

    def wait(self, url: str) -> None:
        dom = urlparse(url).netloc
        if dom in self.seen:
            self.sleep(self.interval)
        self.seen.add(dom)


def _pub_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        d = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _record_health(engine, source: str, now: datetime, items_new: int, rate: float | None,
                   alert: bool, robots_txt: str | None) -> None:
    rh = hashlib.sha256(robots_txt.encode()).hexdigest() if robots_txt is not None else None
    with engine.begin() as c:
        c.execute(sa.text(
            "INSERT INTO source_health(source, checked_at, items_new, extraction_rate, alert, robots_hash) "
            "VALUES (:s,:t,:i,:e,:a,:r) ON CONFLICT (source, checked_at) DO NOTHING"),
            {"s": source, "t": now, "i": items_new, "e": rate, "a": alert, "r": rh})


def _known(engine, source: str, url: str) -> bool:
    with engine.connect() as c:
        return c.execute(sa.text("SELECT 1 FROM raw_message WHERE source=:s AND url=:u LIMIT 1"),
                         {"s": source, "u": url}).first() is not None


def _store(engine, source, url, content, observed, pub, gap):
    raw = C.store_raw(engine=engine, source=source, url=url, content=content, collected_at=None, observed_at=observed)
    rid = getattr(raw, "id", None)
    with engine.begin() as c:
        c.execute(sa.text("UPDATE raw_message SET published_at=:p, published_vs_capture_gap=:g WHERE id=:i"),
                  {"p": pub, "g": gap, "i": rid})
    return rid


def run_source(engine, cfg: dict[str, str], *, http_get, sleep, now: datetime) -> dict[str, Any]:
    source, feed_url, mode = cfg["source"], cfg["feed"], cfg["mode"]
    pacer = _Pacer(sleep)
    robots_url = f"https://{source}/robots.txt"
    pacer.wait(robots_url)
    status, robots_txt = http_get(robots_url)
    if status in (404, 410):
        status, robots_txt = 200, ""
    if status != 200:
        _record_health(engine, source, now, 0, None, True, None)
        return {"status": "robots_unavailable", "items_new": 0, "offers": 0}
    if not C.robots_allowed(robots_txt, feed_url):
        _record_health(engine, source, now, 0, None, True, robots_txt)
        return {"status": "robots_disallowed", "items_new": 0, "offers": 0}

    pacer.wait(feed_url)
    status, body = http_get(feed_url)
    items = C.parse_feed(body) if status == 200 else None
    if items is None:
        _record_health(engine, source, now, 0, None, True, robots_txt)
        return {"status": "feed_unavailable", "items_new": 0, "offers": 0}

    new = offers = failures = 0
    for it in items:
        link, title = it.get("link"), (it.get("title") or "").strip()
        if not link or not title or _known(engine, source, link):
            continue
        pub = _pub_date(it.get("pubDate"))
        observed = min(pub, now) if pub is not None else now
        gap = bool(pub is not None and now - pub > timedelta(days=GAP_DAYS))
        if mode == "titles":
            content = title  # decisao 002: nunca o corpo
        else:
            if not C.robots_allowed(robots_txt, link):
                continue
            pacer.wait(link)
            st, html = http_get(link)
            if st != 200 or not html:
                failures += 1
                continue
            content = html
        rid = _store(engine, source, link, content, observed, pub, gap)
        new += 1
        if mode == "titles":
            res = C.process_raw_message(engine, {"content": title, "id": rid, "source": source}, first_seen_at=observed)
            offers += len(res)
        else:
            from preditor.backfill import _process_snippets

            offers += _process_snippets(engine, source, rid, content, observed)
    alert = failures > 0 and new == 0
    _record_health(engine, source, now, new, (offers / new) if new else None, alert, robots_txt)
    return {"status": "ok", "items_new": new, "offers": offers, "failures": failures}


def run_once(engine, sources: list[dict[str, str]] | None = None, *, http_get=None, sleep=None,
             now: datetime | None = None, run_pipeline: bool = True) -> dict[str, dict[str, Any]]:
    http_get = http_get or _http_get
    sleep = sleep or time.sleep
    now = now or datetime.now(UTC)
    out: dict[str, dict[str, Any]] = {}
    for cfg in (sources if sources is not None else FEEDS):
        out[cfg["source"]] = run_source(engine, cfg, http_get=http_get, sleep=sleep, now=now)
    if run_pipeline and any(v.get("offers") for v in out.values()):
        from preditor.jobs.daily_predict import run_daily

        run_daily(engine=engine)
    return out


def source_status(engine, now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """Por fonte: ultima coleta bem-sucedida, falhas consecutivas e atraso (horas desde o ultimo item)."""
    now = now or datetime.now(UTC)
    res: dict[str, dict[str, Any]] = {}
    with engine.connect() as c:
        rows = c.execute(sa.text(
            "SELECT source, checked_at, alert FROM source_health ORDER BY source, checked_at DESC")).all()
        last_item = dict(c.execute(sa.text(
            "SELECT source, max(observed_at) FROM raw_message GROUP BY source")).all())
    by_src: dict[str, list] = {}
    for s, t, a in rows:
        by_src.setdefault(s, []).append((t, a))
    for s, lst in by_src.items():
        fails = 0
        for _t, a in lst:
            if a:
                fails += 1
            else:
                break
        ok = next((t for t, a in lst if not a), None)
        li = last_item.get(s)
        res[s] = {
            "last_checked_at": lst[0][0],
            "last_success_at": ok,
            "consecutive_failures": fails,
            "last_item_at": li,
            "delay_hours": round((now - li).total_seconds() / 3600, 2) if li else None,
        }
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Listener recorrente de feeds (1 req/10 s, robots fail-closed)")
    ap.add_argument("--once", action="store_true", help="roda uma vez e sai (agendar por cron)")
    ap.add_argument("--no-pipeline", action="store_true")
    ap.add_argument("--database-url", default=None)
    args = ap.parse_args(argv)
    import os

    url = args.database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL ausente")
    engine = sa.create_engine(url)
    out = run_once(engine, run_pipeline=not args.no_pipeline)
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0 if all(v["status"] == "ok" for v in out.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
