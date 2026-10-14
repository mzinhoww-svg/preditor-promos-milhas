"""Protege bancos com dados reais: os testes nao podem escrever neles.

Bancos listados em PREDITOR_PROTECTED_DBS (padrao: preditor_p2, com o backfill real) fazem os
testes com banco serem pulados. Use outro banco (ex.: preditor_p2_test) em DATABASE_URL.
"""
from __future__ import annotations

import os
import warnings

_PROTECTED = {d.strip() for d in os.environ.get("PREDITOR_PROTECTED_DBS", "preditor_p2").split(",") if d.strip()}


def _db_name(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?")[0]


_url = os.environ.get("DATABASE_URL")
if _url and _db_name(_url) in _PROTECTED:
    warnings.warn(f"DATABASE_URL aponta para banco protegido {_db_name(_url)!r}; testes com banco serao pulados", stacklevel=1)
    os.environ.pop("DATABASE_URL", None)
