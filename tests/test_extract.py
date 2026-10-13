from pathlib import Path

import pytest

from preditor.extract import (
    BONUS_PCT_RE,
    Offer,
    cross_check,
    detect_bonus_conflict,
    extract,
    normalize,
    validate_offer,
)

FIX = Path("tests/fixtures")


def read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_normalize_nfkc_and_collapse():
    assert normalize("a   b\nc") == "a b c"


def test_bonus_regex_at_100_and_90():
    assert BONUS_PCT_RE.search("até 100% de bônus") 
    assert 100 in [int(m.group(1) or m.group(2)) for m in BONUS_PCT_RE.finditer("até 100% de bônus")]
    assert 90 in [int(m.group(1) or m.group(2)) for m in BONUS_PCT_RE.finditer("90% de bônus")]


def test_extract_simple_bonus():
    off = extract(read("promo_simples.txt")).ofertas[0]
    # 'Livelo e Smiles' não afirma direção (QA S3)
    assert off.origem is None
    assert off.destino is None
    assert off.tipo == "transfer_bonus"
    assert off.bonus_pct == 90
    assert off.inicio == "2025-03-10"
    assert off.fim == "2025-03-15"


def test_extract_ate_100():
    off = extract(read("promo_ate_100_bonus.txt")).ofertas[0]
    assert off.bonus_pct == 100


def test_extract_clube_segmentado():
    off = extract(read("promo_90_clube.txt")).ofertas[0]
    assert off.bonus_pct == 90
    assert off.segmentada is True
    assert off.segmento == "clube"


def test_extract_range_extenso_soma_plus():
    off = extract(read("promo_range_extenso.txt")).ofertas[0]
    assert off.bonus_pct == 90
    assert off.segmentada is True


def test_extract_no_promo_empty():
    assert extract(read("promo_sem_promocao.txt")).ofertas == []


def test_prompt_injection_ignored():
    off = extract(read("promo_prompt_injection.txt")).ofertas[0]
    assert off.bonus_pct == 85


def test_invalid_date_discarded():
    ex = extract(read("promo_data_invalida.txt"))
    assert ex.ofertas == []


def test_no_pct():
    off = extract(read("promo_sem_percentual.txt")).ofertas[0]
    assert off.bonus_pct is None


def test_strict_schema_forbids_extra():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        Offer(origem="livelo", extra_field=1)


def test_cross_check():
    off = extract(read("promo_simples.txt")).ofertas[0]
    assert cross_check(read("promo_simples.txt"), off) is True


def test_validate_offer_invalid_date():
    off = Offer(origem="livelo", destino="smiles", tipo="transfer_bonus", bonus_pct=90, inicio="2025-02-31", fim=None)
    ok, reasons = validate_offer(off)
    assert ok is False
    assert "inicio_invalido" in reasons


def test_n1_inverted_explicit_year_does_not_roll():
    off = extract("Livelo para Smiles: 90% de bônus de 15/03/2025 a 10/03/2025.").ofertas[0]
    assert off.inicio == "2025-03-15"
    assert off.fim == "2025-03-10"
    ok, reasons = validate_offer(off)
    assert ok is False
    assert "fim_antes_inicio" in reasons


def test_n2_only_end_has_no_inicio():
    off = extract("Livelo para Smiles: 90% de bônus até 15/03/2025.").ofertas[0]
    assert off.inicio is None
    assert off.fim == "2025-03-15"


def test_n3_conflicting_bonus_flagged():
    text = "Livelo para Smiles: bônus de 60% de 10/03/2025 a 15/03/2025. Também 80% de bônus."
    assert detect_bonus_conflict(text) is True
    off = extract(text).ofertas[0]
    assert off.segmento == "bonus_conflitante"


def test_n4_single_program_purchase_destination_and_film_not_offer():
    film = extract("Filme Smiles de 90% de aprovação.").ofertas
    assert film == []
    off = extract("Smiles: compra de pontos com 40% de desconto de 10/03/2025 a 15/03/2025.").ofertas[0]
    assert off.origem is None
    assert off.destino == "smiles"
    assert off.tipo == "purchase_discount"
