"""QA cruzado T10a: ataques ao job diario e a API. Requer DATABASE_URL (banco proprio) e PREDITOR_API_KEY."""
import os, json, threading
from datetime import date, datetime, timedelta, UTC
from sqlalchemy import text
os.environ.setdefault("PREDITOR_API_KEY", "k")
from preditor.api.db import get_engine
from preditor.jobs.daily_predict import run_daily
from preditor.api.queries import fetch_prediction_accuracy
from fastapi.testclient import TestClient
from preditor.api import create_app
E = get_engine()
if os.getenv("QA_SHIM"):  # contorna o TypeError do autor SOMENTE para explorar o restante (nao altera o codigo do autor)
    import preditor.jobs.daily_predict as dp
    _orig = dp.predict_proba
    dp.predict_proba = lambda **kw: _orig(**{k: v for k, v in kw.items() if k not in ("segmented", "segment_label")})
def q(sql, **p):
    with E.connect() as c: return [dict(r._mapping) for r in c.execute(text(sql), p)]
def x(sql, **p):
    with E.begin() as c: c.execute(text(sql), p)
def show(t, v): print(f"[{t}] {v}")
x("DELETE FROM prediction"); 
try: x("DELETE FROM model_run WHERE FALSE")
except Exception: pass
# --- 0 banco vazio
show("A0 job em banco vazio", run_daily(as_of="2026-06-01", engine=E))
show("A0 model_run criado sem dados", q("SELECT count(*) n FROM model_run"))
# --- seed
x("DELETE FROM offer")
def offer(o,d,s,bp,seg=False,lab="", seen=None):
    x("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES(:o,:d,'transfer_bonus',:s,:b,:g,:l,:f)",
      o=o,d=d,s=s,b=bp,g=seg,l=lab,f=seen or datetime.combine(s,datetime.min.time(),UTC))
base=date(2025,1,1)
for i in range(30): offer("Livelo","Smiles",base+timedelta(days=i*10),80)      # b1
for i in range(3): offer("Esfera","LATAM Pass",base+timedelta(days=i*60),100)    # b0
offer("Livelo","Smiles",date(2026,5,1),90,True,"clube")
# oferta FUTURA em relacao ao as_of (vazamento?)
offer("Livelo","Smiles",date(2026,6,10),999)
ASOF="2026-06-01"
r1=run_daily(as_of=ASOF, engine=E); show("A1 run1", r1)
snap1=q("SELECT origin,destination,horizon_days,probability,model_version FROM prediction_log ORDER BY 1,2,3")
r2=run_daily(as_of=ASOF, engine=E); show("A1 run2 (reexecucao)", r2)
show("A1 prediction_log linhas apos 2 runs", q("SELECT count(*) n FROM prediction_log"))
show("A1 prediction linhas", q("SELECT count(*) n FROM prediction"))
# --- vazamento: remover oferta futura nao deve mudar prob
p_with=q("SELECT probability FROM prediction_log WHERE origin='Livelo' AND destination='Smiles' AND horizon_days=7 AND model_version='B1'")
x("DELETE FROM offer WHERE bonus_pct=999"); x("DELETE FROM prediction_log WHERE FALSE") if False else None
# nao da para deletar log (append-only) -> usar as_of diferente com mesmos dados
show("A2 logs B1 Livelo->Smiles 7d (com oferta futura presente)", p_with)
try:
    x("DELETE FROM prediction_log"); show("A2 DELETE em prediction_log", "PERMITIDO (falha)")
except Exception as e: show("A2 DELETE prediction_log", "bloqueado: "+str(e.orig).splitlines()[0])
# --- concorrencia
def go(): run_daily(as_of="2026-06-02", engine=E)
ts=[threading.Thread(target=go) for _ in range(6)]; [t.start() for t in ts]; [t.join() for t in ts]
dup=q("SELECT origin,destination,event_type,horizon_days,model_version,count(*) c FROM prediction_log WHERE logged_at::date='2026-06-02' GROUP BY 1,2,3,4,5 HAVING count(*)>1")
show("A3 concorrencia 6 jobs mesmo dia: grupos duplicados em prediction_log", len(dup))
show("A3 model_run champions", q("SELECT count(*) n, count(*) FILTER (WHERE is_champion) ch FROM model_run"))
# --- acuracia com predicoes ainda nao resolvidas
today=date.today()
run_daily(as_of=str(today), engine=E)
try:
    acc=fetch_prediction_accuracy(date_from=str(today), date_to=str(today)); show("A4 from/to", json.dumps(acc["by_horizon"]))
except Exception as e: show("A4 fetch_prediction_accuracy(from,to)", f"EXCECAO {type(e).__name__}: {e}")
acc=fetch_prediction_accuracy()
show("A4 accuracy sem filtro (logs de hoje ainda abertos contam como erro)", json.dumps({h:v for h,v in acc["by_horizon"].items()}))
# vazamento: job com/sem oferta futura (start_at > as_of) deve dar mesma prob
offs=dp_fetch=[o for o in __import__("preditor.jobs.daily_predict",fromlist=["x"]).fetch_offers(E)]
import preditor.jobs.daily_predict as dp
from preditor.baseline import predict_proba as pp
recs=[o for o in offs if o["origin"]=="Livelo" and not o["segmented"]]
a=pp(records=recs,origin="Livelo",destination="Smiles",event_type="transfer_bonus",method="b1",as_of=date(2026,6,1),horizons=(7,15,30))
b=pp(records=[o for o in recs if o["start_at"]<=date(2026,6,1)],origin="Livelo",destination="Smiles",event_type="transfer_bonus",method="b1",as_of=date(2026,6,1),horizons=(7,15,30))
show("A5 vazamento: prob com/sem oferta futura (as_of 2026-06-01; futura=2026-06-10)", (a==b, a, b))
# first_seen_at posterior ao as_of
x("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,first_seen_at) VALUES('Livelo','Smiles','transfer_bonus','2026-05-20',70,'2026-07-01')")
recs=[o for o in dp.fetch_offers(E) if o["origin"]=="Livelo" and not o["segmented"]]
c2=pp(records=recs,origin="Livelo",destination="Smiles",event_type="transfer_bonus",method="b1",as_of=date(2026,6,1),horizons=(7,15,30))
show("A5b oferta com start<=as_of mas first_seen_at>as_of altera a prob? (conhecimento point-in-time)", (c2==a, c2))
x("DELETE FROM offer WHERE bonus_pct=70 AND first_seen_at>'2026-06-30'")
# --- API
app=create_app()
H={"X-API-Key":"k"}
with TestClient(app, raise_server_exceptions=False) as c:
    show("B1 /predictions", c.get("/v1/predictions",headers=H).status_code)
    j=c.get("/v1/predictions",headers=H).json()
    it=j["items"][0] if j["items"] else None
    show("B1 item0", json.dumps(it)[:600])
    show("B1 modelo", j["model"])
    seg=[i for i in j["items"] if i["pair"]["origin"]=="Livelo"]
    show("B1 linhas Livelo->Smiles (segmentado deve ser separado)", [(i["segmented"],i["segment_label"],i["windows"]["30"]["probability"]) for i in seg])
    show("B2 type invalido", c.get("/v1/predictions?type=xx",headers=H).status_code)
    show("B2 limit=0", len(c.get("/v1/predictions?limit=0",headers=H).json()["items"]))
    show("B2 limit=-1", c.get("/v1/predictions?limit=-1",headers=H).status_code)
    show("B2 limit=abc", c.get("/v1/predictions?limit=abc",headers=H).status_code)
    m=c.get("/v1/model/metrics",headers=H).json()
    show("B3 metrics comparison", m["comparison"]); show("B3 champion", json.dumps(m["champion"])[:300])
    show("B4 from=ontem", c.get("/v1/prediction-log/accuracy?from=ontem",headers=H).status_code); show("B4 from=2026-01-01 (valido)", c.get("/v1/prediction-log/accuracy?from=2026-01-01",headers=H).status_code)
    show("B4 horizon=99", c.get("/v1/prediction-log/accuracy?horizon=99",headers=H).json()["by_horizon"])
    a=c.get("/v1/prediction-log/accuracy",headers=H).json(); show("B4 accuracy", json.dumps(a)[:500])
    show("B5 sem chave", c.get("/v1/predictions").status_code)
    show("B5 chave invalida", c.get("/v1/predictions",headers={"X-API-Key":"zzz"}).status_code)
    show("B5 /docs aberto sem chave", c.get("/docs").status_code)
    show("B5 /openapi.json sem chave", c.get("/openapi.json").status_code)
    os.environ["RATE_LIMIT_PER_MINUTE_KEY"]="5"
    codes=[c.get("/v1/source-health",headers=H).status_code for _ in range(8)]
    show("B6 rate limit (limite 5)", codes)
    codes=[c.get("/v1/source-health",headers={"X-API-Key":f"bad{i}"}).status_code for i in range(3)]
    show("B6 chaves invalidas diferentes", codes)
    show("B6 entradas no limiter por chave arbitraria", len(__import__("preditor.api.limiter",fromlist=["x"])._key_hits))
x("DELETE FROM source_health WHERE FALSE")
