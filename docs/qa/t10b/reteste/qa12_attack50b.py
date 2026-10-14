import datetime as dt, json, os, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor.jobs import daily_predict as J
from preditor import backfill as B, stop as ST
E = create_engine(os.environ["DATABASE_URL"]); R = {}
UTC = dt.UTC; D = dt.date
tmp = Path(tempfile.mkdtemp()); os.chdir(tmp); STOPF = tmp / "STOP"
def q(sql, **p):
    with E.connect() as c: return c.execute(text(sql), p).all()
def ex(sql, **p):
    with E.begin() as c: c.execute(text(sql), p)
# ---- L3 reprocess com 6 campanhas distintas
for t in ("alert", "prediction", "offer_evidence", "offer", "raw_message"):
    try: ex(f"DELETE FROM {t}")
    except Exception: pass
ART = "<html><article><p>A Smiles está oferecendo até {b}% de bônus nas transferências de pontos da Livelo. A oferta é válida de {d1} a {d2}.</p></article></html>"
for i in range(6):
    d1 = (D(2026, 1, 1) + dt.timedelta(days=30 * i)); d2 = d1 + dt.timedelta(days=5)
    ex("INSERT INTO raw_message(source,url,content,content_hash,observed_at) VALUES ('x.test',:u,:c,:h,:o)",
       u=f"https://x.test/r{i}/", c=ART.format(b=70 + i, d1=d1.strftime("%d/%m"), d2=d2.strftime("%d/%m")), h=f"h{i}", o=dt.datetime.combine(d1, dt.time(10), tzinfo=UTC))
B.reprocess(E); full = q("select count(*) from offer")[0][0]
k = []; orig = B._process_snippets
def ps(*a, **kw):
    k.append(1)
    if len(k) == 4: STOPF.write_text("x")
    return orig(*a, **kw)
B._process_snippets = ps
try: B.reprocess(E); res = "NAO"
except ST.StopRequested: res = "StopRequested"
B._process_snippets = orig; STOPF.unlink(missing_ok=True)
R["L3_reprocess_meio_6_campanhas"] = {"res": res, "ofertas_antes": full, "ofertas_apos": q("select count(*) from offer")[0][0], "evidencias": q("select count(*) from offer_evidence")[0][0],
                                      "estado": "BANCO PARCIAL: ofertas apagadas e nao reconstruidas" if q("select count(*) from offer")[0][0] < full else "integro"}
# ---- campeao sobrevive
for t in ("alert", "prediction", "offer_evidence", "offer", "raw_message"):
    try: ex(f"DELETE FROM {t}")
    except Exception: pass
ex("UPDATE model_run SET is_champion=FALSE")
mr = q("INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, hyperparams, metrics, code_hash, is_champion) VALUES ('C1', now(), 't08b-ds','1','{}'::jsonb,'{}'::jsonb,'t08b',TRUE) RETURNING id") if False else None
with E.begin() as c:
    champ = c.execute(text("INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, hyperparams, metrics, code_hash, is_champion) VALUES ('C1', now(), 't08b-ds','1','{}'::jsonb,'{}'::jsonb,'t08b',TRUE) RETURNING id")).scalar()
for i in range(4): ex("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES ('ch_a','ch_b','transfer_bonus',:s,80,false,'',:f) ON CONFLICT DO NOTHING", s=D(2026, 1, 1) + dt.timedelta(days=30 * i), f=dt.datetime(2026, 1, 1, tzinfo=UTC))
r1 = J.run_daily(as_of="2026-06-01", engine=E)
ex("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES ('ch_a','ch_b','transfer_bonus','2026-05-10',80,false,'','2026-05-10')")
r2 = J.run_daily(as_of="2026-06-02", engine=E)
rows = q("select id, model_version, role, is_champion from model_run order by id")
R["C1_campeao"] = {"champion_id": champ, "runs": [tuple(r) for r in rows], "campeao_intacto": [r for r in rows if r[0] == champ][0][3] is True,
                   "daily_nunca_champion": all((not r[3]) for r in rows if r[2] == "daily"), "n_champions": sum(1 for r in rows if r[3])}
# API model/metrics
os.environ["PREDITOR_API_KEY"] = "k"
from fastapi.testclient import TestClient
from preditor.api import create_app
with TestClient(create_app()) as cl:
    m = cl.get("/v1/model/metrics", headers={"X-API-Key": "k"}).json()
    R["C2_api_champion"] = {"name": m["champion"]["name"], "version": m["champion"].get("version"), "esperado_do_T08b": "C1"}
# run legado (pre-0007) marcado champion pelo job antigo: role default 'experiment'?
ex("INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, hyperparams, metrics, code_hash, is_champion) VALUES ('B0', now(), 'legado','1','{\"name\":\"B0\",\"methods\":{}}'::jsonb,'{}'::jsonb,'legacy',TRUE)")
R["C3_run_legado_do_job_antigo"] = [tuple(r) for r in q("select model_version, role, is_champion from model_run where dataset_version='legado'")]
# ---- concorrencia: 8 threads x 5 rodadas
dups = []
for rnd in range(5):
    o, d = f"cc{rnd}_a", f"cc{rnd}_b"
    for i in range(4): ex("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES (:o,:d,'transfer_bonus',:s,80,false,'',:f) ON CONFLICT DO NOTHING", o=o, d=d, s=D(2026, 1, 1) + dt.timedelta(days=30 * i), f=dt.datetime(2026, 1, 1, tzinfo=UTC))
    errs = []; ids = []
    def j():
        try: ids.append(J.run_daily(as_of=D(2026, 7, 1) + dt.timedelta(days=rnd), engine=E)["model_run_id"])
        except Exception as e: errs.append(repr(e)[:90])
    ts = [threading.Thread(target=j) for _ in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
    dups.append({"rodada": rnd, "ids_distintos": sorted(set(ids)), "erros": errs[:1],
                 "grupos_duplicados": q("select count(*) from (select model_version,dataset_version,code_hash,count(*) from model_run where role='daily' group by 1,2,3 having count(*)>1) x")[0][0],
                 "champions": q("select count(*) from model_run where is_champion")[0][0],
                 "pred_dup": q("select count(*) from (select made_at,model_run_id,origin,destination,event_type,horizon_days,count(*) from prediction group by 1,2,3,4,5,6 having count(*)>1) x")[0][0],
                 "log_dup": q("select count(*) from (select model_version,origin,destination,event_type,horizon_days,(logged_at at time zone 'UTC')::date,count(*) from prediction_log group by 1,2,3,4,5,6 having count(*)>1) x")[0][0],
                 "alertas_dup": q("select count(*) from (select made_at,origin,destination,event_type,horizon_days,threshold,count(*) from alert group by 1,2,3,4,5,6 having count(*)>1) x")[0][0]})
R["K_concorrencia"] = dups
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
