from datetime import date

import pytest

from preditor.campaigns import Evidence, consolidate, same_campaign


def ev(source, d):
    return Evidence(source=source, start_at=date.fromisoformat(d))


def test_single_source_is_not_validated_and_has_reduced_weight():
    c = consolidate([ev("pdp", "2026-03-10")])
    assert c.n_sources == 1
    assert c.validated is False
    assert c.weight == 0.5
    assert c.start_at == date(2026, 3, 10)
    assert c.date_conflict is False


def test_two_sources_within_three_days_validate_and_use_earliest_date():
    c = consolidate([ev("pdp", "2026-03-12"), ev("mc", "2026-03-10")])
    assert c.n_sources == 2
    assert c.validated is True
    assert c.weight == 1.0
    assert c.start_at == date(2026, 3, 10)
    assert c.date_conflict is True  # datas divergem, mesmo dentro da janela


def test_same_date_two_sources_has_no_conflict():
    c = consolidate([ev("pdp", "2026-03-10"), ev("mc", "2026-03-10")])
    assert c.validated is True
    assert c.date_conflict is False


def test_sources_more_than_three_days_apart_are_conflict_not_validated():
    c = consolidate([ev("pdp", "2026-03-01"), ev("mc", "2026-03-10")])
    assert c.validated is False
    assert c.date_conflict is True
    assert c.start_at == date(2026, 3, 1)
    assert c.weight == 0.5


def test_repeated_messages_from_same_source_do_not_count_as_sources():
    c = consolidate([ev("pdp", "2026-03-10"), ev("pdp", "2026-03-10")])
    assert c.n_sources == 1
    assert c.validated is False


def test_empty_evidence_is_rejected():
    with pytest.raises(ValueError):
        consolidate([])


def test_same_campaign_uses_key_and_three_day_window():
    k = ("livelo", "smiles", "transfer_bonus")
    assert same_campaign(k, date(2026, 3, 10), k, date(2026, 3, 13))
    assert not same_campaign(k, date(2026, 3, 10), k, date(2026, 3, 14))
    other = ("livelo", "azul", "transfer_bonus")
    assert not same_campaign(k, date(2026, 3, 10), other, date(2026, 3, 10))
