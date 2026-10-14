import argparse, datetime as dt, json, os, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor.jobs import daily_predict as J
from preditor import collector as C, backfill as B, stop as ST
from preditor.api import queries as Qs
E = create_engine(os.environ["DATABASE_URL"]); R = {}
UTC = dt.UTC; D = dt.date
def wipe():
    with E.begin() as c:
        for t in ("alert", "prediction", "offer_evidence", "offer", "raw_message", "source_health"):
            try: c.execute(text(f"DELETE FROM {t}"))
            except Exception: pass
        try: c.execute(text("DELETE FROM model_run WHERE id NOT IN (SELECT DISTINCT model_run_id FROM prediction_log WHERE model_run_id IS NOT NULL)"))
        except Exception: pass
def offer(o, d, start, bonus=80, fs=None):
    fs = fs or dt.datetime.combine(start, dt.time.min, tzinfo=UTC)
    with E.begin() as c:
        c.execute(text("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES(:o,:d,'transfer_bonus',:s,:b,false,'',:f) ON CONFLICT DO NOTHING"), dict(o=o, d=d, s=start, b=bonus, f=fs))
def seed(n=4, o="livelo", d="smiles", step=30, y0=2026, m0=1):
    for i in range(n): offer(o, d, D(y0, m0, 1) + dt.timedelta(days=step * i))
def cnt(tabs=("prediction", "prediction_log", "model_run", "alert", "raw_message", "source_health")):
    with E.connect() as c: return {t: c.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in tabs}
def stop_off(): 
    for k in ("PREDITOR_STOP", "PREDITOR_STOP_FILE"): os.environ.pop(k, None)
tmp = Path(tempfile.mkdtemp()); os.chdir(tmp)
# ---------------- STOP
wipe(); seed(); stop_off(); before = cnt()
(tmp / "STOP").write_text("x")
try: J.run_daily(as_of="2026-06-01", engine=E); R["S1_job_STOP_arquivo_cwd"] = "NAO abortou"
except ST.StopRequested: R["S1_job_STOP_arquivo_cwd"] = {"abortou": True, "igual": cnt() == before}
(tmp / "STOP").unlink()
os.environ["PREDITOR_STOP"] = "1"
try: J.run_daily(as_of="2026-06-01", engine=E); R["S2_job_STOP_env"] = "NAO abortou"
except ST.StopRequested: R["S2_job_STOP_env"] = {"abortou": True, "igual": cnt() == before}
os.environ["PREDITOR_STOP"] = "0"; R["S2b_env_0_nao_para"] = (not ST.stop_requested())
os.environ["PREDITOR_STOP"] = ""; os.environ["PREDITOR_STOP_FILE"] = str(tmp / "OUTRO")
(tmp / "OUTRO").write_text("x")
try: J.run_daily(as_of="2026-06-01", engine=E); R["S3_STOP_FILE_override"] = "NAO abortou"
except ST.StopRequested: R["S3_STOP_FILE_override"] = True
(tmp / "STOP").write_text("x"); R["S3b_override_ignora_STOP_do_cwd"] = (not (ST.stop_requested() and False)) and (not ST.stop_requested() is False)
(tmp / "OUTRO").unlink(); (tmp / "STOP").unlink(); stop_off()
# CLI exit code
import subprocess
(tmp / "STOP").write_text("x")
r = subprocess.run([sys.executable, "-m", "preditor.jobs.daily_predict", "daily", "--as-of", "2026-06-01"], cwd=tmp, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": os.environ["SRC50"]})
R["S4_cli_exit"] = (r.returncode, (r.stdout + r.stderr)[-120:]); (tmp / "STOP").unlink()
# coletor: collect_rss / backfill (collector) / run_backfill (CLI real) / collect_titles_rss / collect_archived_feed
(tmp / "STOP").write_text("x"); before = cnt()
def tryrun(name, f):
    try: f(); R[name] = {"abortou": False, "gravou": cnt() != before}
    except ST.StopRequested: R[name] = {"abortou": True, "gravou": cnt() != before}
    except Exception as e: R[name] = {"abortou": f"outra excecao {type(e).__name__}: {str(e)[:60]}", "gravou": cnt() != before}
FEED = "<?xml version='1.0'?><rss><channel><item><title>Smiles oferece 80% de bônus da Livelo</title><link>https://x.test/a/</link><pubDate>Wed, 14 Oct 2026 10:00:00 +0000</pubDate></item></channel></rss>"
class Tr:
    def fetch(self, url): return FEED if "robots" not in url else "User-agent: *\nDisallow:\n"
tryrun("C1_collect_rss", lambda: C.collect_rss(engine=E, source="x.test", url="https://x.test/feed/", transport=Tr()))
tryrun("C2_collector.backfill", lambda: C.backfill(engine=E, source="x.test", from_="202301", transport=Tr()))
B.STATE_PATH = tmp / "state.json"
time_sleep = time.sleep; time.sleep = lambda s: None
B.fetch_robots_strict = lambda s: ("ok", "User-agent: *\nDisallow:\n")
B.fetch_cdx_candidates = lambda *a, **k: [{"url": "https://x.test/p1/", "timestamp": "20260101120000"}]
B.fetch_snapshot_backoff = lambda ts, u: "<html><article><p>A Smiles está oferecendo até 90% de bônus nas transferências de pontos da Livelo. A oferta é válida somente até amanhã (15).</p></article></html>"
args = argparse.Namespace(from_="202301", to=None, rate_limit=10.0, sources=["x.test"], database_url=os.environ["DATABASE_URL"], refresh_candidates=False, max_attempts=3, titles_only=False, page_size=500, slug_mode="either", max_fetch=None)
tryrun("C3_backfill.run_backfill(CLI real)", lambda: B.run_backfill(args))
B.fetch_robots_strict = lambda s: ("ok", "User-agent: *\nDisallow:\n")
B.list_feed_captures = lambda *a, **k: [{"timestamp": "20260101120000", "original": "https://x.test/feed/"}]
B.fetch_snapshot_backoff = lambda ts, u: FEED
tryrun("C4_collect_archived_feed", lambda: B.collect_archived_feed(E, "x.test", "https://x.test/feed/", D(2025, 1, 1)))
tryrun("C5_collect_titles_rss", lambda: B.collect_titles_rss(E, "x.test", "https://x.test/feed/"))
(tmp / "STOP").unlink()
# STOP no meio do job (apos iniciar)
wipe(); stop_off()
for i, (o, d) in enumerate([("livelo", "smiles"), ("esfera", "latam"), ("itau", "azul"), ("c6", "tudo")]): seed(4, o, d)
orig_pp = J.predict_proba; calls = []
def pp(*a, **k):
    calls.append(1)
    if len(calls) == 1: (tmp / "STOP").write_text("x")
    return orig_pp(*a, **k)
J.predict_proba = pp
try:
    out = J.run_daily(as_of="2026-06-01", engine=E); R["S5_STOP_no_meio"] = {"abortou": False, "pares": out["pairs"], "gravou_pred": cnt()["prediction"]}
except ST.StopRequested: R["S5_STOP_no_meio"] = {"abortou": True, "gravou_pred": cnt()["prediction"]}
J.predict_proba = orig_pp; (tmp / "STOP").unlink(missing_ok=True)
# ---------------- model_run
wipe(); stop_off(); seed(4, 'mr_a', 'mr_b')
r1 = J.run_daily(as_of="2026-06-01", engine=E); r2 = J.run_daily(as_of="2026-06-01", engine=E)
with E.connect() as c: mr = c.execute(text("SELECT id, model_version, dataset_version, code_hash, metrics, hyperparams, is_champion FROM model_run ORDER BY id")).mappings().all()
R["M1_reexec_mesmo_run"] = {"ids": (r1["model_run_id"], r2["model_run_id"]), "n_model_run": len(mr), "campos": {k: str(v)[:60] for k, v in dict(mr[-1]).items()}}
offer("mr_a", "mr_b", D(2026, 5, 1)); r3 = J.run_daily(as_of="2026-06-01", engine=E)
with E.connect() as c: n_mr = c.execute(text("SELECT count(*), count(*) filter (where is_champion) FROM model_run")).first()
R["M2_novos_dados_novo_run"] = {"id": r3["model_run_id"], "n_model_run_champion": tuple(n_mr), "predicoes_mesmo_dia": cnt()["prediction"]}
with E.connect() as c: R["M2b_prediction_mesmo_made_at_runs"] = [tuple(r) for r in c.execute(text("SELECT model_run_id, count(*) FROM prediction GROUP BY 1 ORDER BY 1"))]
# concorrencia: 6 jobs simultaneos em dia novo com dados novos
wipe(); seed(4, 'cc_a', 'cc_b'); errs = []
def j():
    try: J.run_daily(as_of="2026-07-01", engine=E)
    except Exception as ex: errs.append(repr(ex)[:90])
ts = [threading.Thread(target=j) for _ in range(6)]; [t.start() for t in ts]; [t.join() for t in ts]
with E.connect() as c:
    R["M3_concorrencia"] = {"erros": errs[:2], "n_model_run": c.execute(text("SELECT count(*) FROM model_run")).scalar(),
                            "champions": c.execute(text("SELECT count(*) FROM model_run WHERE is_champion")).scalar(),
                            "predicoes": c.execute(text("SELECT count(*) FROM prediction")).scalar(), "alertas": c.execute(text("SELECT count(*) FROM alert")).scalar()}
# ---------------- alertas
os.environ["PREDITOR_ALERT_THRESHOLD"] = "0.5"
wipe()
# serie com probabilidade variando: usa predicoes inseridas direto para controlar cruzamento
with E.begin() as c:
    mr0 = c.execute(text("INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, hyperparams, metrics, code_hash, is_champion) VALUES ('B0', now(), 'qa','1','{}'::jsonb,'{}'::jsonb,'qa',TRUE) RETURNING id")).scalar()
    for day, p in ((1, 0.30), (2, 0.55), (3, 0.60), (4, 0.40), (5, 0.70)):
        for h in (7, 15, 30):
            c.execute(text("INSERT INTO prediction (made_at, model_run_id, origin, destination, event_type, horizon_days, probability) VALUES (:m,:r,'livelo','smiles','transfer_bonus',:h,:p)"),
                      dict(m=dt.datetime(2026, 10, day, tzinfo=UTC), r=mr0, h=h, p=p))
from preditor.alerts import register_alerts
n = [register_alerts(E, dt.datetime(2026, 10, d, tzinfo=UTC)) for d in (1, 2, 3, 4, 5)]
R["A1_cruzamentos_por_dia"] = n  # esperado: [0, 3, 0, 0, 3]
n2 = [register_alerts(E, dt.datetime(2026, 10, d, tzinfo=UTC)) for d in (1, 2, 3, 4, 5)]
R["A2_idempotente_reexec"] = {"novos": n2, "total": cnt()["alert"]}
register_alerts(E, dt.datetime(2026, 10, 2, tzinfo=UTC), threshold=0.5); R["A2b_total_apos_mesma_thr"] = cnt()["alert"]
register_alerts(E, dt.datetime(2026, 10, 2, tzinfo=UTC), threshold=0.52); R["A3_novo_limiar_cria_outro"] = cnt()["alert"]
for bad in ("abc", "1.5", "-1", "0", "nan"):
    os.environ["PREDITOR_ALERT_THRESHOLD"] = bad
    from preditor.alerts import alert_threshold
    R.setdefault("A4_limiar_invalido", {})[bad] = alert_threshold()
os.environ["PREDITOR_ALERT_THRESHOLD"] = "0.5"
# prob exatamente no limiar; prev == limiar
with E.begin() as c:
    for h in (7, 15, 30):
        c.execute(text("INSERT INTO prediction (made_at, model_run_id, origin, destination, event_type, horizon_days, probability) VALUES (:m,:r,'esfera','latam','transfer_bonus',:h,0.5)"), dict(m=dt.datetime(2026, 10, 6, tzinfo=UTC), r=mr0, h=h))
R["A5_prob_igual_limiar_sem_anterior"] = register_alerts(E, dt.datetime(2026, 10, 6, tzinfo=UTC))
# preenchimento retroativo: rodar dia 3 depois de ter dia 4 e 5
R["A6_retroativo_dia3"] = register_alerts(E, dt.datetime(2026, 10, 3, tzinfo=UTC))
R["A7_sem_canal_externo"] = [m for m in ("telegram", "smtplib", "requests", "httpx", "urllib.request", "slack") if m in open(__import__("preditor.alerts",fromlist=["x"]).__file__).read().lower()]
# API
os.environ["PREDITOR_API_KEY"] = "k"
from fastapi.testclient import TestClient
from preditor.api import create_app
with TestClient(create_app()) as cl:
    H = {"X-API-Key": "k"}
    a = cl.get("/v1/alerts", headers=H); R["API_alerts"] = (a.status_code, len(a.json().get("items", [])), a.json()["items"][:1])
    R["API_alerts_limit"] = {l: cl.get(f"/v1/alerts?limit={l}", headers=H).status_code for l in (0, 1, 500, 501, "x")}
    R["API_alerts_sem_key"] = cl.get("/v1/alerts").status_code
    R["API_expl_inexistente"] = cl.get("/v1/predictions/zzz/yyy/explanation", headers=H).status_code
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
