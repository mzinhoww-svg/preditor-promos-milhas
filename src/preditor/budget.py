"""Contador de orçamento: consulta antes de cada chamada paga e interrompe no teto."""
from __future__ import annotations

from typing import Protocol


class BudgetExceeded(RuntimeError):
    pass


class Ledger(Protocol):
    def total(self, provider: str) -> float: ...
    def add(self, provider: str, amount_brl: float) -> None: ...


class InMemoryLedger:
    def __init__(self) -> None:
        self._t: dict[str, float] = {}

    def total(self, provider: str) -> float:
        return self._t.get(provider, 0.0)

    def add(self, provider: str, amount_brl: float) -> None:
        self._t[provider] = self.total(provider) + amount_brl


class SqlLedger:
    """Ledger persistente na tabela budget_ledger (uma linha por gasto)."""

    def __init__(self, engine) -> None:
        self._engine = engine

    def total(self, provider: str) -> float:
        from sqlalchemy import text

        with self._engine.connect() as c:
            return float(
                c.execute(
                    text("SELECT COALESCE(SUM(amount_brl),0) FROM budget_ledger WHERE provider=:p"),
                    {"p": provider},
                ).scalar_one()
            )

    def add(self, provider: str, amount_brl: float) -> None:
        from sqlalchemy import text

        with self._engine.begin() as c:
            c.execute(
                text("INSERT INTO budget_ledger(provider, amount_brl) VALUES (:p, :a)"),
                {"p": provider, "a": amount_brl},
            )


class Budget:
    def __init__(self, ledger: Ledger, caps: dict[str, float]) -> None:
        self._ledger = ledger
        self._caps = caps

    def spent(self, provider: str) -> float:
        return self._ledger.total(provider)

    def charge(self, provider: str, amount_brl: float) -> None:
        """Chame ANTES da chamada paga, com o custo estimado. Levanta se passar do teto."""
        if amount_brl < 0:
            raise ValueError("custo negativo")
        cap = self._caps.get(provider)
        if cap is None:
            raise BudgetExceeded(f"{provider}: sem teto configurado")
        if self._ledger.total(provider) + amount_brl > cap + 1e-9:
            raise BudgetExceeded(f"{provider}: teto de R$ {cap:.2f} atingido")
        self._ledger.add(provider, amount_brl)
