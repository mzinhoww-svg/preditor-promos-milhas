"""Oferta cuja unica evidencia tem published_vs_capture_gap nao entra em treino nem avaliacao."""
from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text

from preditor import model as M


def mk(start, gap_only=False):
    return {"origin": "livelo", "destination": "smiles", "event_type": "transfer_bonus",
            "start_at": start, "first_seen_at": start, "gap_only": gap_only}


def synth(gap_only=False, n=52):
    d0 = date(2023, 1, 1)
    return [mk(d0 + timedelta(days=i * 15 + (i * 7) % 5), gap_only) for i in range(n)]


def test_exclude_gap_only_helper():
    recs = [mk(date(2024, 1, 1), True), mk(date(2024, 2, 1), False)]
    assert len(M.exclude_gap_only(recs)) == 1


def test_evaluate_ignores_gap_only_records():
    with pytest.raises(ValueError):
        M.evaluate_c1_vs_b1(synth(gap_only=True), data_source="real")


def test_evaluate_runs_when_not_gap_only():
    out = M.evaluate_c1_vs_b1(synth(gap_only=False), data_source="real", n_boot=20)
    assert "gate_inputs" in out


URL_DB = os.environ.get("DATABASE_URL")


@pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")
def test_daily_job_fetch_offers_skips_gap_only_offers(db_at_head):
    from preditor.jobs.daily_predict import fetch_offers

    e = create_engine(URL_DB)

    def clean():
        with e.begin() as c:
            for t in ("offer_evidence", "offer", "raw_message"):
                c.execute(text(f"DELETE FROM {t}"))

    clean()
    try:
        with e.begin() as c:
            for i, gap in ((1, True), (2, False)):
                rid = c.execute(text(
                    "INSERT INTO raw_message(source,url,content,content_hash,collected_at,observed_at,"
                    "published_vs_capture_gap) VALUES ('s','u'||:i,'c','h'||:i,now(),now(),:g) RETURNING id"),
                    {"i": i, "g": gap}).scalar_one()
                oid = c.execute(text(
                    "INSERT INTO offer(origin,destination,event_type,start_at,end_at,bonus_pct,segmented,"
                    "segment_label,first_seen_at,n_sources,validated,date_conflict,weight) VALUES "
                    "('livelo','smiles','transfer_bonus',:s,null,80,false,'',now(),1,false,false,0.5) RETURNING id"),
                    {"s": date(2024, i, 1)}).scalar_one()
                c.execute(text("INSERT INTO offer_evidence(offer_id,raw_message_id,source,seen_start_at) "
                               "VALUES (:o,:r,'s',:s)"), {"o": oid, "r": rid, "s": date(2024, i, 1)})
        assert len(fetch_offers(e)) == 1
    finally:
        clean()
