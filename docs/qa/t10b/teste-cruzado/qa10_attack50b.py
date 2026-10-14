import datetime as dt, json, os, sys, threading
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor.jobs import daily_predict as J
E = create_engine(os.environ["DATABASE_URL"]); R = {}
UTC = dt.UTC; D = dt.date
def offer(o, d, start, bonus=80, fs=None):
    fs = fs or dt.datetime.combine(start, dt.time.min, tzinfo=UTC)
    with E.begin() as c:
        c.execute(text("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES(:o,:d,'transfer_bonus',:s,:b,false,'',:f) ON CONFLICT DO NOTHING"), dict(o=o, d=d, s=start, b=bonus, f=fs))
def expl(o, d, madeat):
    with E.connect() as c:
        r = c.execute(text("SELECT explanation FROM prediction WHERE origin=:o AND destination=:d AND made_at=:m AND horizon_days=7 ORDER BY model_run_id DESC LIMIT 1"), dict(o=o, d=d, m=madeat)).first()
    return r[0] if r else None
# ---- explicacao sem vazamento
for i in range(4): offer("ex_a", "ex_b", D(2026, 1, 1) + dt.timedelta(days=30 * i))
offer("ex_a", "ex_b", D(2026, 5, 1), bonus=300, fs=dt.datetime(2026, 9, 1, tzinfo=UTC))      # backfill tardio: start<=as_of, visto depois
offer("ex_a", "ex_b", D(2026, 7, 15), bonus=250)                                              # start futuro
as_of = D(2026, 6, 1); made = dt.datetime(2026, 6, 1, tzinfo=UTC)
J.run_daily(as_of=as_of, engine=E); e1 = expl("ex_a", "ex_b", made)
R["E1_explicacao_as_of_2026-06-01"] = {k: e1[k] for k in ("as_of", "method", "n_campaigns", "last_campaign_start", "days_since_last", "median_interval_days")}
R["E1_sem_vazamento"] = (e1["n_campaigns"] == 4 and e1["last_campaign_start"] == "2026-04-01")
# dados novos depois + job de data posterior: explicacao antiga imutavel?
offer("ex_a", "ex_b", D(2026, 8, 1)); J.run_daily(as_of=D(2026, 9, 1), engine=E)
e1b = expl("ex_a", "ex_b", made); R["E2_explicacao_antiga_inalterada"] = (e1 == e1b)
e2 = expl("ex_a", "ex_b", dt.datetime(2026, 9, 1, tzinfo=UTC)); R["E2b_explicacao_nova"] = {k: e2[k] for k in ("as_of", "n_campaigns", "last_campaign_start", "days_since_last")}
# reexecucao retroativa do mesmo as_of apos novos dados: explicacao recalculada? (ON CONFLICT DO NOTHING -> nao muda)
J.run_daily(as_of=as_of, engine=E); R["E3_reexec_retroativa_mantem"] = (expl("ex_a", "ex_b", made) == e1)
# API explanation
os.environ["PREDITOR_API_KEY"] = "k"
from fastapi.testclient import TestClient
from preditor.api import create_app
with TestClient(create_app()) as cl:
    H = {"X-API-Key": "k"}
    r = cl.get("/v1/predictions/ex_a/ex_b/explanation", headers=H); R["API_explanation"] = (r.status_code, r.json())
    R["API_explanation_type_invalido"] = cl.get("/v1/predictions/ex_a/ex_b/explanation?type=zzz", headers=H).status_code
    # ---- source health coerencia
    now = dt.datetime.now(UTC)
    rows = [("fonte_a", now - dt.timedelta(hours=1), 3, 0.5, False, "h1"), ("fonte_a", now - dt.timedelta(hours=30), 2, 0.7, False, "h1"),
            ("fonte_a", now - dt.timedelta(days=3), 5, 0.6, False, "h0"), ("fonte_a", now - dt.timedelta(days=9), 7, None, False, "h0"),
            ("fonte_b", now - dt.timedelta(hours=2), 0, None, True, None), ("fonte_b", now - dt.timedelta(hours=26), 4, 0.9, False, "x1"),
            ("fonte_c", now - dt.timedelta(hours=1), 1, 0.4, False, "z"), ("fonte_c", now - dt.timedelta(hours=1, minutes=-1), 1, 0.4, False, "z")]
    with E.begin() as c:
        c.execute(text("DELETE FROM source_health"))
        for s, t, i, er, a, h in rows:
            c.execute(text("INSERT INTO source_health(source,checked_at,items_new,extraction_rate,alert,robots_hash) VALUES(:s,:t,:i,:e,:a,:h)"), dict(s=s, t=t, i=i, e=er, a=a, h=h))
    sh = cl.get("/v1/source-health", headers=H).json()
    R["SH"] = {s["source"]: {k: s[k] for k in ("status", "items_new_24h", "items_new_7d", "extraction_rate_7d", "error_rate_24h", "robots_hash", "robots_changed", "last_success_at", "last_item_at", "message")} for s in sh["sources"]}
    # esperado fonte_a: 24h=3, 7d=3+2+5=10, extraction media (0.5+0.7+0.6)/3=0.6, robots h1 vs h0? prev_hash = proximo com hash != ... 
# ---- corrida de model_run (sem UNIQUE): 8 threads x 5 rodadas em datasets novos
dups = []
for rnd in range(5):
    o, d = f"rc{rnd}_a", f"rc{rnd}_b"
    for i in range(4): offer(o, d, D(2026, 1, 1) + dt.timedelta(days=30 * i))
    errs = []
    def j():
        try: J.run_daily(as_of=D(2026, 6, 1) + dt.timedelta(days=rnd), engine=E)
        except Exception as ex: errs.append(repr(ex)[:80])
    ts = [threading.Thread(target=j) for _ in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
    with E.connect() as c:
        n = c.execute(text("SELECT count(*) FROM (SELECT model_version,dataset_version,code_hash,count(*) FROM model_run GROUP BY 1,2,3 HAVING count(*)>1) x")).scalar()
        ch = c.execute(text("SELECT count(*) FROM model_run WHERE is_champion")).scalar()
    dups.append({"rodada": rnd, "grupos_duplicados": n, "champions": ch, "erros": errs[:1]})
R["MR_corrida"] = dups
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
