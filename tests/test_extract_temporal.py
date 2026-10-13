
from datetime import UTC, date, datetime

from preditor.extract import _collect_dates, extract


def one(text, fs):
    ex = extract(text, first_seen_at=fs)
    assert ex.ofertas, f"sem oferta: {text}"
    return ex.ofertas[0]

T1 = "Livelo para Smiles com 100% de bônus na transferência de 30/12 a 05/01."
def test_Y1_virada_basica():
    o = one(T1, date(2025, 12, 28)); assert (o.inicio, o.fim) == ("2025-12-30", "2026-01-05")
def test_Y2_virada_tz_utc():
    o = one(T1, datetime(2026, 1, 1, 2, 30, tzinfo=UTC)); assert o.inicio == "2025-12-30"
def test_Y3_inicio_janeiro_visto_em_dezembro():
    o = one("Livelo para Smiles com 90% de bônus na transferência a partir de 02/01.", date(2025, 12, 29)); assert o.inicio == "2026-01-02"
def test_Y4_so_fim_janeiro_visto_em_dezembro():
    o = one("Livelo para Smiles com 90% de bônus na transferência até 05/01.", date(2025, 12, 29)); assert o.fim == "2026-01-05"
def test_Y5_visto_em_janeiro_inicio_dezembro():
    o = one(T1, date(2026, 1, 2)); assert (o.inicio, o.fim) == ("2025-12-30", "2026-01-05")
def test_L1_sem_first_seen_nao_usa_hoje():
    ex = extract("Livelo para Smiles com 100% de bônus na transferência de 10/03 a 15/03.")
    o = ex.ofertas[0] if ex.ofertas else None
    assert o is None or (o.inicio is None and o.fim is None)
def test_L2_determinismo_independe_de_hoje():
    assert _collect_dates("de 10/03 a 15/03", None) == []
def test_N1_destino_inventado_com_um_programa():
    o = one("Livelo oferece 100% de bônus na transferência até 15/03.", date(2025, 3, 1)); assert o.destino is None and o.origem is None
def test_N2_sem_percentual_bonus_none():
    o = one("Livelo para Smiles: bônus na transferência de 10/03 a 15/03.", date(2025, 3, 1)); assert o.bonus_pct is None
def test_N3_sem_datas_none():
    o = one("Livelo para Smiles com 100% de bônus na transferência.", date(2025, 3, 1)); assert o.inicio is None and o.fim is None
def test_N4_tipo_nao_inventado():
    ex = extract("Livelo e Smiles anunciam parceria de 10/03 a 15/03.", first_seen_at=date(2025, 3, 1))
    assert not ex.ofertas or ex.ofertas[0].tipo is None
def test_B1_bissexto_sem_ano():
    o = one("Livelo para Smiles com 100% de bônus na transferência de 27/02 a 29/02.", date(2024, 2, 20)); assert o.fim == "2024-02-29"
def test_B2_29fev_ano_nao_bissexto_descarta_inteiro():
    ex = extract("Livelo para Smiles com 100% de bônus na transferência de 27/02 a 01/03. Regulamento 29/02.", first_seen_at=date(2025, 2, 20))
    assert ex.ofertas
def test_F1_fs_string_datetime_iso():
    o = one(T1, "2025-12-28T10:00:00-03:00"); assert o.inicio == "2025-12-30"
