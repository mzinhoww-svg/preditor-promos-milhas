"""Loader de registros do T08: preenche gap_only a partir das evidencias (GAP_ONLY_SQL)."""
from __future__ import annotations

import os
from datetime import UTC, date

import pytest
from sqlalchemy import create_engine, text

from preditor import model as M
from preditor.records import load_offer_records

URL_DB = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")


def _clean(e):
    with e.begin() as c:
        for t in ("offer_evidence", "offer", "raw_message"):
            c.execute(text(f"DELETE FROM {t}"))


def _mk(c, i, gaps):
    oid = c.execute(text(
        "INSERT INTO offer(origin,destination,event_type,start_at,end_at,bonus_pct,segmented,segment_label,"
        "first_seen_at,n_sources,validated,date_conflict,weight) VALUES "
        "('livelo','smiles','transfer_bonus',:s,null,80,false,'',now(),1,false,false,0.5) RETURNING id"),
        {"s": date(2024, i, 1)}).scalar_one()
    for k, g in enumerate(gaps):
        rid = c.execute(text(
            "INSERT INTO raw_message(source,url,content,content_hash,collected_at,observed_at,published_vs_capture_gap) "
            "VALUES ('s',:u,'c',:h,now(),now(),:g) RETURNING id"),
            {"u": f"u{i}-{k}", "h": f"h{i}-{k}", "g": g}).scalar_one()
        c.execute(text("INSERT INTO offer_evidence(offer_id,raw_message_id,source,seen_start_at) VALUES (:o,:r,'s',:d)"),
                  {"o": oid, "r": rid, "d": date(2024, i, 1)})


def test_loader_marks_gap_only_and_exclude_drops_them(db_at_head):
    e = create_engine(URL_DB)
    _clean(e)
    try:
        with e.begin() as c:
            _mk(c, 1, [True])           # so gap  -> gap_only
            _mk(c, 2, [True, False])    # tem evidencia limpa -> entra
            _mk(c, 3, [False])
        recs = load_offer_records(e)
        by_month = {r["start_at"].month: r["gap_only"] for r in recs}
        assert by_month == {1: True, 2: False, 3: False}
        assert len(M.exclude_gap_only(recs)) == 2
    finally:
        _clean(e)


def test_mixed_offer_first_seen_uses_only_non_gap_evidence(db_at_head):
    from datetime import datetime

    e = create_engine(URL_DB)
    _clean(e)
    try:
        with e.begin() as c:
            oid = c.execute(text(
                "INSERT INTO offer(origin,destination,event_type,start_at,end_at,bonus_pct,segmented,segment_label,"
                "first_seen_at,n_sources,validated,date_conflict,weight) VALUES "
                "('livelo','smiles','transfer_bonus','2024-03-01',null,80,false,'','2020-01-01',2,true,false,1) RETURNING id"
            )).scalar_one()
            for k, (gap, obs) in enumerate([(True, "2020-01-01T00:00:00+00:00"), (False, "2024-03-01T12:00:00+00:00")]):
                rid = c.execute(text(
                    "INSERT INTO raw_message(source,url,content,content_hash,collected_at,observed_at,"
                    "published_vs_capture_gap) VALUES ('s',:u,'c',:h,now(),:o,:g) RETURNING id"),
                    {"u": f"m{k}", "h": f"m{k}", "o": obs, "g": gap}).scalar_one()
                c.execute(text("INSERT INTO offer_evidence(offer_id,raw_message_id,source,seen_start_at) "
                               "VALUES (:o,:r,'s','2024-03-01')"), {"o": oid, "r": rid})
        rec = load_offer_records(e)[0]
        assert rec["gap_only"] is False
        assert rec["first_seen_at"] == datetime(2024, 3, 1, 12, tzinfo=UTC)
    finally:
        _clean(e)


def test_loader_does_not_expose_final_state_fields(db_at_head):
    e = create_engine(URL_DB)
    _clean(e)
    try:
        with e.begin() as c:
            _mk(c, 1, [False])
        rec = load_offer_records(e)[0]
        assert "validated" not in rec and "n_sources" not in rec
    finally:
        _clean(e)
