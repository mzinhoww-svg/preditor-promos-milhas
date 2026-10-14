"""Causa raiz: _first_seen_dt recebe o registro inteiro (dict) em vez de first_seen_at -> sempre None."""
from datetime import date, datetime, UTC
from preditor import model as M
r={"origin":"a","destination":"b","event_type":"transfer_bonus","start_at":date(2024,1,1),"first_seen_at":datetime(2024,1,1,tzinfo=UTC)}
print("_first_seen_dt(registro) =", M._first_seen_dt(r))
print("_first_seen_dt(registro['first_seen_at']) =", M._first_seen_dt(r["first_seen_at"]))
g=M.build_daily_grade([r,{**r,"start_at":date(2024,2,1),"first_seen_at":datetime(2024,2,1,tzinfo=UTC)}],horizons=[7])
print("grade: n_known_offers distintos =", sorted({x["n_known_offers"] for x in g}), "| days_since_last distintos =", sorted({x["days_since_last_offer"] for x in g}))
