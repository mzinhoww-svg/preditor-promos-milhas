"""Gera docs/reports/t08b-champion-decision.md a partir da avaliação walk-forward.

Uso: python scripts/t08b_report.py [caminho_saida]
Sem banco com campanhas reais o relatório sai rotulado como SINTÉTICO.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

from preditor.model import run_champion_challenger


def synthetic_records(n: int = 52, step: int = 15) -> list[dict]:
    d0 = date(2023, 1, 1)
    out = []
    for i in range(n):
        s = d0 + timedelta(days=i * step + (i * 7) % 5)
        out.append({"origin": "livelo", "destination": "smiles",
                    "event_type": "transfer_bonus", "start_at": s,
                    "first_seen_at": s, "synthetic": True})
    return out


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/reports/t08b-champion-decision.md"
    res = run_champion_challenger(
        synthetic_records(), data_source="synthetic", report_path=path, n_boot=500
    )
    print(res["decision"]["decision"], res["decision"]["reasons"])
