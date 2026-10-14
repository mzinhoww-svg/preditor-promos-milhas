"""Configuração da API via variáveis de ambiente."""
from __future__ import annotations

import os


def api_key() -> str:
    return (os.getenv("PREDITOR_API_KEY") or "").strip()


def database_url() -> str | None:
    return os.getenv("DATABASE_URL")


def cors_allowed_origins() -> list[str]:
    raw = os.getenv("PREDITOR_CORS_ORIGINS", os.getenv("CORS_ALLOWED_ORIGINS", ""))
    return [o.strip() for o in raw.split(",") if o.strip()]


def rate_limit_key_per_minute() -> int:
    try:
        return int(os.getenv("RATE_LIMIT_PER_MINUTE_KEY", "60"))
    except ValueError:
        return 60


def rate_limit_ip_per_minute() -> int:
    try:
        return int(os.getenv("RATE_LIMIT_PER_MINUTE_IP", "120"))
    except ValueError:
        return 120
