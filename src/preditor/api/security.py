"""Autenticação por X-API-Key com comparacao em tempo constante."""
from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _expected_key() -> str:
    return (os.getenv("PREDITOR_API_KEY") or "").strip()


def require_api_key(request: Request, api_key: str | None = Security(API_KEY_HEADER)) -> str:
    expected = _expected_key()
    if not expected:
        raise HTTPException(status_code=503, detail={"error": {"code": "NOT_CONFIGURED", "message": "API indisponível"}})
    if not api_key:
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "X-API-Key ausente"}})
    if not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "X-API-Key inválida"}})
    request.state.api_key = api_key
    return api_key
