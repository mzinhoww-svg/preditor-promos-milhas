"""QA T10a reteste 3 (0d55bab): ataques point-in-time/idempotência/concorrência. Banco proprio."""
import datetime as dt, os, threading, json
from datetime import datetime
from sqlalchemy import text
UTC = dt.UTC; D = dt.date
from preditor.api.db import get_engine
from preditor.jobs.daily_predict import run_daily
e = get_engine()
def wipe():
    with e.begin() as c:
        c.execute(text("DELETE FROM prediction")); c.execute(text("DELETE FROM offer")); c.execute(text("DELETE FROM model_run"))
def offer(o,d,start,fs=None,bonus=80,seg=False,lab=""):
    fs = fs or datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    with e.begin() as c:
        c.execute(text("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES(:o,:d,'transfer_bonus',:s,:b,:g,:l,:f)"),
                  dict(o=o,d=d,s=start,b=bonus,g=seg,l=lab,f=fs))
def preds():
    with e.connect() as c:
        return [tuple(r) for r in c.execute(text("SELECT origin,destination,horizon_days,probability,bonus_p25,bonus_p50,bonus_p75 FROM prediction ORDER BY 1,2,3"))]
def logs():
    with e.connect() as c:
        return c.execute(text("SELECT count(*) FROM prediction_log")).scalar()
R = {}
# A1: oferta com start<=as_of mas first_seen > as_of (descoberta tardia/backfill) nao pode mudar nada
wipe()
for i in range(4): offer("livelo","smiles",D(2026,1,1)+dt.timedelta(days=30*i), bonus=60)
run_daily(as_of="2026-06-01", engine=e); base = preds()
wipe()
for i in range(4): offer("livelo","smiles",D(2026,1,1)+dt.timedelta(days=30*i), bonus=60)
offer("livelo","smiles",D(2026,5,20), fs=datetime(2026,9,1,tzinfo=UTC), bonus=300)   # backfill tardio, bonus enorme
offer("esfera","latam",D(2026,5,25), fs=datetime(2026,9,1,tzinfo=UTC), bonus=100)    # par so conhecido depois
run_daily(as_of="2026-06-01", engine=e); r = preds()
R["A1_backfill_tardio_nao_vaza"] = (r == base)
R["A1_par_tardio_ausente"] = all(p[0]!="esfera" for p in r)
# A2: oferta futura (start > as_of) com first_seen <= as_of (anuncio antecipado) - nao deve entrar (start>as_of)
wipe()
for i in range(4): offer("livelo","smiles",D(2026,1,1)+dt.timedelta(days=30*i), bonus=60)
offer("livelo","smiles",D(2026,7,1), fs=datetime(2026,5,1,tzinfo=UTC), bonus=300)
run_daily(as_of="2026-06-01", engine=e); r2 = preds()
R["A2_anuncio_futuro_nao_entra_no_bonus"] = (r2 == base)
# A3: first_seen exatamente na fronteira (as_of 00:00) -> conhecido; 1s depois -> nao
wipe()
for i in range(4): offer("livelo","smiles",D(2026,1,1)+dt.timedelta(days=30*i), bonus=60)
offer("livelo","smiles",D(2026,5,31), fs=datetime(2026,6,1,0,0,1,tzinfo=UTC), bonus=300)
run_daily(as_of="2026-06-01", engine=e)
R["A3_fronteira_1s_depois_nao_entra"] = (preds()==base)
# A4: reexecucao idempotente
n1, l1 = len(preds()), logs()
run_daily(as_of="2026-06-01", engine=e)
R["A4_reexec_idempotente"] = (len(preds())==n1 and logs()==l1)
# A5: concorrencia 6 jobs
wipe()
for i in range(4): offer("livelo","smiles",D(2026,1,1)+dt.timedelta(days=30*i))
errs=[]
def j():
    try: run_daily(as_of="2026-06-01", engine=e)
    except Exception as ex: errs.append(str(ex)[:100])
ts=[threading.Thread(target=j) for _ in range(6)]; [t.start() for t in ts]; [t.join() for t in ts]
with e.connect() as c:
    dup = c.execute(text("SELECT count(*) FROM (SELECT origin,destination,event_type,horizon_days,count(*) c FROM prediction_log GROUP BY 1,2,3,4 HAVING count(*)>1) x")).scalar()
R["A5_concorrencia_dups"] = dup; R["A5_erros"] = errs[:3]
# A6: banco vazio / as_of antes de qualquer oferta
wipe(); 
try:
    out = run_daily(as_of="2020-01-01", engine=e); R["A6_vazio"] = ("ok", len(preds()))
except Exception as ex: R["A6_vazio"] = ("EXC", str(ex)[:120])
# A7: as_of futuro distante com ofertas -> nao deve explodir
for i in range(4): offer("livelo","smiles",D(2026,1,1)+dt.timedelta(days=30*i))
try:
    run_daily(as_of="2030-01-01", engine=e); R["A7_futuro"]=("ok", len(preds()))
except Exception as ex: R["A7_futuro"]=("EXC", str(ex)[:120])
# A8: serve predicao mais recente apos dois dias de job
wipe()
for i in range(4): offer("livelo","smiles",D(2026,1,1)+dt.timedelta(days=30*i))
run_daily(as_of="2026-06-01", engine=e)
offer("livelo","smiles",D(2026,6,2), bonus=90); offer("livelo","smiles",D(2026,6,3), bonus=90)
run_daily(as_of="2026-06-10", engine=e)
os.environ["PREDITOR_API_KEY"]="k"
from fastapi.testclient import TestClient
from preditor.api import create_app
with TestClient(create_app()) as cl:
    j = cl.get("/v1/predictions", headers={"X-API-Key":"k"}).json()
    R["A8_items"] = len(j["items"]); R["A8_made_at"] = sorted({str(i.get("made_at")) for i in j["items"]})
    R["A8_status"] = {p: cl.get(p, headers={"X-API-Key":"k"}).status_code for p in ("/v1/predictions?limit=-1","/v1/predictions?type=zzz","/v1/accuracy?from=ontem","/v1/accuracy","/v1/weekly","/v1/alerts","/health")}
print(json.dumps(R, indent=1, default=str))
