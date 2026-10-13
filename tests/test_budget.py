import pytest

from preditor.budget import Budget, BudgetExceeded, InMemoryLedger


def test_records_spend_and_blocks_at_cap():
    b = Budget(InMemoryLedger(), caps={"openrouter": 10.0})
    b.charge("openrouter", 6.0)
    b.charge("openrouter", 4.0)
    assert b.spent("openrouter") == 10.0
    with pytest.raises(BudgetExceeded):
        b.charge("openrouter", 0.01)
    assert b.spent("openrouter") == 10.0  # chamada barrada não grava gasto


def test_unknown_provider_without_cap_is_refused():
    b = Budget(InMemoryLedger(), caps={})
    with pytest.raises(BudgetExceeded):
        b.charge("apify", 1.0)


def test_negative_cost_rejected():
    b = Budget(InMemoryLedger(), caps={"openrouter": 10.0})
    with pytest.raises(ValueError):
        b.charge("openrouter", -1)
