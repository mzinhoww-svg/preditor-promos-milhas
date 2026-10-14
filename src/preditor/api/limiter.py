"""Rate limit simples em memoria por chave e por IP."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

from .settings import rate_limit_ip_per_minute, rate_limit_key_per_minute

_lock = Lock()
_key_hits: dict[str, deque[float]] = defaultdict(deque)
_ip_hits: dict[str, deque[float]] = defaultdict(deque)


def _trim(window: deque[float], now: float, limit_window: int = 60) -> None:
    while window and now - window[0] > limit_window:
        window.popleft()


def check_rate_limit(request: Request, api_key: str) -> None:
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    key_limit = rate_limit_key_per_minute()
    ip_limit = rate_limit_ip_per_minute()
    with _lock:
        _trim(_key_hits[api_key], now)
        _trim(_ip_hits[ip], now)
        if len(_key_hits[api_key]) >= key_limit:
            raise HTTPException(status_code=429, detail={"error": {"code": "RATE_LIMITED", "message": "Limite por chave excedido"}})
        if len(_ip_hits[ip]) >= ip_limit:
            raise HTTPException(status_code=429, detail={"error": {"code": "RATE_LIMITED", "message": "Limite por IP excedido"}})
        _key_hits[api_key].append(now)
        _ip_hits[ip].append(now)
