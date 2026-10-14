import datetime as dt, json, os, sys
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor.jobs import daily_predict as J
E = create_engine(os.environ["DATABASE_URL"]); UTC = dt.UTC; D = dt.date; R = {}
def ex(sql, **p):
    with E.begin() as c: return c.execute(text(sql), p)
for t in ("alert", "prediction", "offer_evidence", "offer"):
    try: ex(f"DELETE FROM {t}")
    except Exception: pass
ex("UPDATE model_run SET is_champion=FALSE")
with E.begin() as c:
    champ = c.execute(text("INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, hyperparams, metrics, code_hash, is_champion, role) VALUES ('C1', now(), 'rc-t08b','1','{\"name\":\"C1\",\"version\":\"2.0.0\"}'::jsonb,'{}'::jsonb,'t08b',TRUE,'experiment') RETURNING id")).scalar()
for p in range(2):
    for i in range(4): ex("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES (:o,:d,'transfer_bonus',:s,80,false,'',:f)", o=f"Api{p}", d="Smiles", s=D(2026, 1, 1) + dt.timedelta(days=30 * i), f=dt.datetime(2026, 1, 1, tzinfo=UTC))
r1 = J.run_daily(as_of="2026-06-01", engine=E); r2 = J.run_daily(as_of="2026-06-02", engine=E)
R["run_ids"] = [r1["model_run_id"], r2["model_run_id"]]
R["runs"] = [tuple(r) for r in ex("SELECT id, model_version, role, is_champion FROM model_run ORDER BY id").all()]
os.environ["PREDITOR_API_KEY"] = "k"
from fastapi.testclient import TestClient
from preditor.api import create_app
with TestClient(create_app()) as cl:
    H = {"X-API-Key": "k"}
    p = cl.get("/v1/predictions", headers=H).json()
    R["predictions.model"] = p["model"]; R["predictions.champion"] = p.get("champion")
    R["item_model_run_id"] = sorted({i.get("model_run_id") for i in p["items"]})
    m = cl.get("/v1/model/metrics", headers=H).json()
    R["metrics.champion"] = {k: m["champion"].get(k) for k in ("name", "version", "run_id")}; R["metrics.serving"] = m.get("serving")
    R["metrics.comparison"] = m.get("comparison")
    ex("UPDATE model_run SET is_champion=FALSE")   # sem campeao decidido
    p2 = cl.get("/v1/predictions", headers=H).json(); m2 = cl.get("/v1/model/metrics", headers=H).json()
    R["sem_campeao.predictions.champion"] = p2.get("champion"); R["sem_campeao.metrics.champion_name"] = m2["champion"].get("name"); R["sem_campeao.metrics.serving"] = m2.get("serving", {}) and m2["serving"].get("name")
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
