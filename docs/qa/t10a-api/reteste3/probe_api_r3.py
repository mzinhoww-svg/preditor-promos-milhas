import os, json, threading, datetime as dt
from datetime import datetime
os.environ["PREDITOR_API_KEY"]="k"
from sqlalchemy import text
from preditor.api.db import get_engine
from preditor.jobs.daily_predict import run_daily
e=get_engine()
with e.connect() as c:
    d=c.execute(text("SELECT count(*) FROM (SELECT model_version,origin,destination,event_type,horizon_days,(logged_at AT TIME ZONE 'UTC')::date dia,count(*) FROM prediction_log GROUP BY 1,2,3,4,5,6 HAVING count(*)>1) x")).scalar()
    tot=c.execute(text("SELECT count(*) FROM prediction_log")).scalar()
print("A5 duplicatas logicas (chave do indice) =", d, "de", tot, "linhas")
# 6 jobs concorrentes em dia novo
with e.begin() as c:
    for i in range(4):
        c.execute(text("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES('azul','tudo','transfer_bonus',:s,70,false,'',:f) ON CONFLICT DO NOTHING"),
                  dict(s=dt.date(2026,1,1)+dt.timedelta(days=30*i), f=datetime(2026,1,1,tzinfo=dt.UTC)))
errs=[]
def j():
    try: run_daily(as_of="2026-07-15", engine=e)
    except Exception as ex: errs.append(repr(ex)[:120])
ts=[threading.Thread(target=j) for _ in range(6)]; [t.start() for t in ts]; [t.join() for t in ts]
with e.connect() as c:
    n=c.execute(text("SELECT count(*) FROM prediction_log WHERE (logged_at AT TIME ZONE 'UTC')::date='2026-07-15' AND origin='azul'")).scalar()
print("6 jobs simultaneos: erros", errs, "| linhas azul/tudo em 2026-07-15 =", n, "(esperado 3 horizontes)")
from fastapi.testclient import TestClient
from preditor.api import create_app
with TestClient(create_app()) as cl:
    paths=sorted(cl.get("/openapi.json").json()["paths"])
    print("rotas", paths)
    H={"X-API-Key":"k"}
    for p in paths:
        if "{" in p: continue
        r=cl.get(p,headers=H); print(p, r.status_code, r.text[:90].replace("\n"," "))
    for p in ("/v1/predictions?limit=-1","/v1/accuracy?from=ontem","/v1/accuracy?from=2026-01-01&to=2026-12-31"):
        r=cl.get(p,headers=H); print(p, r.status_code, r.text[:90])
    r=cl.get("/v1/predictions"); print("sem key", r.status_code)
