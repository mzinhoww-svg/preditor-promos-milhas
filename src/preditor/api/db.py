"""Acesso ao Postgres."""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL ausente")
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def reset_engine() -> None:
    global _engine
    _engine = None
