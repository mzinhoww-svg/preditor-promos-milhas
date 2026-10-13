"""Seed idempotente da tabela calendar_event."""

from __future__ import annotations

import os
from datetime import date
from typing import Any

# (nome, tipo, data)
SEED_EVENTS: list[tuple[str, str, date]] = []

# Feriados / datas de varejo (vários anos)
_RETAIL = [
    ("pascoa", "retail", None),
    ("dia_das_maes", "retail", None),
    ("dia_dos_namorados", "retail", date(2024, 6, 12)),
    ("dia_dos_namorados", "retail", date(2025, 6, 12)),
    ("dia_dos_namorados", "retail", date(2026, 6, 12)),
    ("black_friday", "retail", date(2024, 11, 29)),
    ("black_friday", "retail", date(2025, 11, 28)),
    ("black_friday", "retail", date(2026, 11, 27)),
    ("cyber_monday", "retail", date(2024, 12, 2)),
    ("cyber_monday", "retail", date(2025, 12, 1)),
    ("cyber_monday", "retail", date(2026, 11, 30)),
    ("natal", "retail", None),
    ("ano_novo", "retail", None),
]
for name, kind, d in _RETAIL:
    if d is None:
        # gerar recorrentes 2024-2027
        if name == "pascoa":
            for y, dd in (
                (2024, date(2024, 3, 31)),
                (2025, date(2025, 4, 20)),
                (2026, date(2026, 4, 5)),
                (2027, date(2027, 3, 28)),
            ):
                SEED_EVENTS.append((name, kind, dd))
        elif name == "dia_das_maes":
            for y, d2 in (
                (2024, date(2024, 5, 12)),
                (2025, date(2025, 5, 11)),
                (2026, date(2026, 5, 10)),
                (2027, date(2027, 5, 9)),
            ):
                SEED_EVENTS.append((name, kind, d2))
        elif name == "natal":
            for y in range(2023, 2028):
                SEED_EVENTS.append((name, kind, date(y, 12, 25)))
        elif name == "ano_novo":
            for y in range(2023, 2028):
                SEED_EVENTS.append((name, kind, date(y, 1, 1)))
    else:
        SEED_EVENTS.append((name, kind, d))

# Aniversários dos programas (datas de fundação / marcos)
_PROGRAMS = [
    ("livelo_aniversario", "program_anniversary", date(2014, 4, 1)),
    ("smiles_aniversario", "program_anniversary", date(1994, 1, 1)),
    ("azul_fidelidade_aniversario", "program_anniversary", date(2008, 1, 1)),
    ("latam_pass_aniversario", "program_anniversary", date(2019, 1, 1)),
    ("esfera_aniversario", "program_anniversary", date(2018, 1, 1)),
]
for name, kind, d in _PROGRAMS:
    for y in range(2023, 2028):
        SEED_EVENTS.append((name, kind, date(y, d.month, d.day)))

# Black Friday já em _RETAIL; duplicatas removidas no insert.
# dedup interno
_seen = set()
_dedup = []
for name, kind, d in SEED_EVENTS:
    if (name, kind, d) in _seen:
        continue
    _seen.add((name, kind, d))
    _dedup.append((name, kind, d))
SEED_EVENTS = _dedup


def seed_calendar_events(
    engine_or_conn: Any = None, *, database_url: str | None = None
) -> int:
    """Insere SEED_EVENTS de forma idempotente. Retorna quantidade inserida (tentativas)."""
    from sqlalchemy import create_engine, text

    if engine_or_conn is None:
        url = database_url or os.environ.get("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL ausente")
        engine = create_engine(url)
        conn_ctx = engine.begin()
    else:
        # aceita engine ou connection
        if hasattr(engine_or_conn, "begin"):
            conn_ctx = engine_or_conn.begin()
        else:
            # já é connection
            conn_ctx = None
            conn = engine_or_conn

    inserted = 0
    sql = text(
        "INSERT INTO calendar_event(name, kind, event_date) VALUES (:name, :kind, :d) "
        "ON CONFLICT (name, event_date) DO NOTHING"
    )
    if conn_ctx is not None:
        with conn_ctx as c:
            for name, kind, d in SEED_EVENTS:
                c.execute(sql, {"name": name, "kind": kind, "d": d})
                inserted += 1
    else:
        for name, kind, d in SEED_EVENTS:
            conn.execute(sql, {"name": name, "kind": kind, "d": d})
            inserted += 1
    return inserted


def main() -> None:
    seed_calendar_events()
    print(f"seeded {len(SEED_EVENTS)} eventos")


if __name__ == "__main__":
    main()
