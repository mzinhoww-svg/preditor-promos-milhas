"""Reprocessamento do backfill e deduplicacao de prorrogacoes (banco de teste)."""
from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from preditor import backfill as B

URL_DB = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")

FALSE_POS = ('<html><body><aside><p>Azul Fidelidade para Smiles com 110% de bônus até 30/09.</p></aside>'
             '<article><p>Livelo para Smiles com 80% de bônus de 19/03 a 31/03.</p></article></body></html>')


@pytest.fixture
def eng(db_at_head):
    e = create_engine(URL_DB)
    with e.begin() as c:
        c.execute(text("DELETE FROM offer_evidence"))
        c.execute(text("DELETE FROM offer"))
        c.execute(text("DELETE FROM raw_message"))
    yield e
    with e.begin() as c:
        c.execute(text("DELETE FROM offer_evidence"))
        c.execute(text("DELETE FROM offer"))
        c.execute(text("DELETE FROM raw_message"))


def _raw(e, url, html, obs):
    with e.begin() as c:
        c.execute(text("INSERT INTO raw_message(source,url,content,content_hash,collected_at,observed_at) "
                       "VALUES ('passageirodeprimeira.com',:u,:c,:h,now(),:o)"),
                  {"u": url, "c": html, "h": url, "o": obs})


def test_reprocess_ignores_aside_false_positive(eng):
    _raw(eng, "http://a/p", FALSE_POS, datetime(2026, 3, 19, tzinfo=UTC))
    r = B.reprocess(eng)
    with eng.connect() as c:
        rows = c.execute(text("SELECT bonus_pct FROM offer")).scalars().all()
    assert [float(x) for x in rows] == [80.0]
    assert r["new_offers"] == 1


def test_reprocess_skips_rows_without_observed_at(eng):
    _raw(eng, "http://a/p", FALSE_POS, None)
    assert B.reprocess(eng)["new_offers"] == 0


def test_dedupe_merges_extensions(eng):
    with eng.begin() as c:
        for end, seg in (("2026-03-20", "clube"), ("2026-03-31", "bonus_conflitante")):
            c.execute(text("INSERT INTO offer(origin,destination,event_type,start_at,end_at,bonus_pct,segmented,"
                           "segment_label,first_seen_at,n_sources,validated,date_conflict,weight) VALUES "
                           "('livelo','smiles','transfer_bonus','2026-03-19',:e,80,true,:s,now(),1,false,false,0.5)"),
                      {"e": end, "s": seg})
    assert B.dedupe_extensions(eng) == 1
    with eng.connect() as c:
        rows = c.execute(text("SELECT end_at FROM offer")).all()
    assert len(rows) == 1 and str(rows[0][0]) == "2026-03-31"


def test_recompute_gap_flags_old_published_time(eng):
    html = ('<html><head><meta property="article:published_time" content="2023-01-01T10:00:00+00:00"></head>'
            "<body>x</body></html>")
    _raw(eng, "http://a/p", html, datetime(2023, 1, 1, tzinfo=UTC))
    n = B.recompute_gap(eng, {"http://a/p": "20240401000000"})
    assert n == 1
    with eng.connect() as c:
        row = c.execute(text("SELECT published_vs_capture_gap FROM raw_message")).scalar_one()
    assert row is True


def test_end_only_becomes_start_inferred_from_first_seen(eng):
    html = "<html><body><article><p>Livelo para Smiles com 80% de bônus até 31/03.</p></article></body></html>"
    _raw(eng, "http://a/p", html, datetime(2026, 3, 19, 15, 0, tzinfo=UTC))
    B.reprocess(eng)
    with eng.connect() as c:
        row = c.execute(text("SELECT o.start_at, o.end_at, e.start_inferred FROM offer o "
                             "JOIN offer_evidence e ON e.offer_id=o.id")).one()
    assert str(row[0]) == "2026-03-19" and str(row[1]) == "2026-03-31" and row[2] is True


def test_end_only_in_the_past_is_not_an_offer(eng):
    html = "<html><body><article><p>Livelo para Smiles com 80% de bônus até 10/03.</p></article></body></html>"
    _raw(eng, "http://a/p", html, datetime(2026, 3, 19, 15, 0, tzinfo=UTC))
    assert B.reprocess(eng)["new_offers"] == 0


def test_explicit_start_is_not_marked_inferred(eng):
    _raw(eng, "http://a/p", FALSE_POS, datetime(2026, 3, 19, tzinfo=UTC))
    B.reprocess(eng)
    with eng.connect() as c:
        assert c.execute(text("SELECT start_inferred FROM offer_evidence")).scalar_one() is False


def test_recompute_gap_keeps_published_at_of_title_only_rows(eng):
    pub = datetime(2024, 1, 2, 10, tzinfo=UTC)
    _raw(eng, "http://ppv/a", "Livelo e Smiles: 100% de bônus", datetime(2024, 1, 2, 10, tzinfo=UTC))
    with eng.begin() as c:
        c.execute(text("UPDATE raw_message SET published_at=:p, published_vs_capture_gap=true"), {"p": pub})
    B.recompute_gap(eng, {})
    with eng.connect() as c:
        row = c.execute(text("SELECT published_at, published_vs_capture_gap FROM raw_message")).one()
    assert row[0] == pub and row[1] is True


# ---- T10b ciclo 2: reprocess atomico (STOP/erro no meio nao deixa banco parcial) ----
def _html(month: int) -> str:
    return (f'<html><body><article><p>Livelo para Smiles com 80% de bônus de 10/{month:02d} a 15/{month:02d}.'
            f'</p></article></body></html>')


def _seed_old(e):
    with e.begin() as c:
        for d in (3, 4):
            c.execute(text(
                "INSERT INTO offer(origin,destination,event_type,start_at,end_at,bonus_pct,segmented,segment_label,"
                "first_seen_at,n_sources,validated,date_conflict,weight) VALUES "
                "('livelo','smiles','transfer_bonus',:s,:s,100,false,'',now(),1,false,false,1)"),
                {"s": f"2025-0{d}-01"})
    with e.connect() as c:
        return sorted(c.execute(text("SELECT id FROM offer")).scalars().all())


def _six_raws(e):
    for i in range(6):
        _raw(e, f"http://a/p{i}", _html(i + 1), datetime(2026, i + 1, 10, tzinfo=UTC))


def test_reprocess_stop_no_meio_preserva_estado_antigo(eng, tmp_path, monkeypatch):
    from preditor.stop import StopRequested

    stop = tmp_path / "STOP"
    monkeypatch.setenv("PREDITOR_STOP_FILE", str(stop))
    old_ids = _seed_old(eng)
    _six_raws(eng)
    calls = []
    real = B._process_snippets

    def counting(engine, source, rid, content, observed):
        calls.append(rid)
        if len(calls) == 4:
            stop.write_text("")  # STOP no 4o de 6
        return real(engine, source, rid, content, observed)

    monkeypatch.setattr(B, "_process_snippets", counting)
    with pytest.raises(StopRequested):
        B.reprocess(eng)
    assert len(calls) == 4  # parou no meio
    with eng.connect() as c:
        ids = sorted(c.execute(text("SELECT id FROM offer")).scalars().all())
    assert ids == old_ids  # estado antigo intacto (nem 4 de 6 novas, nem vazio)


def test_reprocess_erro_no_meio_faz_rollback(eng, monkeypatch):
    old_ids = _seed_old(eng)
    _six_raws(eng)
    n = {"i": 0}
    real = B._process_snippets

    def boom(engine, source, rid, content, observed):
        n["i"] += 1
        if n["i"] == 3:
            raise RuntimeError("falha simulada")
        return real(engine, source, rid, content, observed)

    monkeypatch.setattr(B, "_process_snippets", boom)
    with pytest.raises(RuntimeError):
        B.reprocess(eng)
    with eng.connect() as c:
        assert sorted(c.execute(text("SELECT id FROM offer")).scalars().all()) == old_ids


def test_reprocess_main_stop_no_meio_rc3_e_estado_antigo(eng, tmp_path, monkeypatch):
    stop = tmp_path / "STOP"
    monkeypatch.setenv("PREDITOR_STOP_FILE", str(stop))
    old_ids = _seed_old(eng)
    _six_raws(eng)
    calls = []
    real = B._process_snippets

    def counting(engine, source, rid, content, observed):
        calls.append(rid)
        if len(calls) == 2:
            stop.write_text("")
        return real(engine, source, rid, content, observed)

    monkeypatch.setattr(B, "_process_snippets", counting)
    assert B.main(["--reprocess", "--database-url", URL_DB]) == 3
    with eng.connect() as c:
        assert sorted(c.execute(text("SELECT id FROM offer")).scalars().all()) == old_ids


def test_reprocess_completo_continua_gerando_ofertas(eng):
    _seed_old(eng)
    _six_raws(eng)
    r = B.reprocess(eng)
    assert r["new_offers"] == 6 and r["old_offers"] == 2
