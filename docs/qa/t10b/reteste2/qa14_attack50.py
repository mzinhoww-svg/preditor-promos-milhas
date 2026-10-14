import datetime as dt, json, os, subprocess, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor import backfill as B, stop as ST
from preditor.jobs import daily_predict as J
E = create_engine(os.environ["DATABASE_URL"]); R = {}
UTC = dt.UTC; D = dt.date
tmp = Path(tempfile.mkdtemp()); os.chdir(tmp); STOPF = tmp / "STOP"
def q(sql, **p):
    with E.connect() as c: return c.execute(text(sql), p).all()
def ex(sql, **p):
    with E.begin() as c: c.execute(text(sql), p)
for t in ("alert", "prediction", "offer_evidence", "offer", "raw_message"):
    try: ex(f"DELETE FROM {t}")
    except Exception: pass
ART = "<html><article><p>A Smiles está oferecendo até {b}% de bônus nas transferências de pontos da Livelo. A oferta é válida de {d1} a {d2}.</p></article></html>"
for i in range(6):
    d1 = D(2026, 1, 1) + dt.timedelta(days=30 * i); d2 = d1 + dt.timedelta(days=5)
    ex("INSERT INTO raw_message(source,url,content,content_hash,observed_at,published_vs_capture_gap) VALUES ('x.test',:u,:c,:h,:o,:g)",
       u=f"https://x.test/r{i}/", c=ART.format(b=70 + i, d1=d1.strftime("%d/%m"), d2=d2.strftime("%d/%m")), h=f"h{i}", o=dt.datetime.combine(d1, dt.time(10), tzinfo=UTC), g=(i % 2 == 0))
B.reprocess(E)
def snap(): return {"offers": q("select count(*) from offer")[0][0], "ev": q("select count(*) from offer_evidence")[0][0],
                    "ids": [r[0] for r in q("select id from offer order by id")], "gaps": [r[0] for r in q("select published_vs_capture_gap from raw_message order by id")]}
base = snap(); R["base"] = {k: v for k, v in base.items() if k != "ids"}
orig = B._process_snippets
def with_hook(n, action):
    k = []
    def ps(*a, **kw):
        k.append(1)
        if len(k) == n: action()
        return orig(*a, **kw)
    B._process_snippets = ps
def stop_action(): STOPF.write_text("x")
def err_action(): raise ValueError("falha de extracao simulada")
# A: STOP no 4o de 6
with_hook(4, stop_action)
try: B.reprocess(E); res = "NAO"
except ST.StopRequested: res = "StopRequested"
B._process_snippets = orig; STOPF.unlink(missing_ok=True); s = snap()
R["A_STOP_4o_de_6"] = {"res": res, "igual_ao_estado_anterior": s == base, "offers": s["offers"], "ev": s["ev"]}
# B: erro no 3o
with_hook(3, err_action)
try: B.reprocess(E); res = "NAO"
except ValueError as e: res = f"ValueError: {e}"
B._process_snippets = orig; s = snap()
R["B_erro_3o"] = {"res": res, "igual_ao_estado_anterior": s == base, "offers": s["offers"]}
# C: recompute_gap falha -> reprocess tambem desfeito (CLI main com estado do backfill vazio)
orig_rg = B.recompute_gap
def rg_boom(*a, **k): raise RuntimeError("recompute_gap falhou")
B.recompute_gap = rg_boom
B.STATE_PATH = tmp / "state.json"
os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"]
# modifica o conteudo de um raw para que a reextracao mude o resultado se NAO houver rollback
ex("UPDATE raw_message SET content = :c WHERE url='https://x.test/r0/'", c="<html><article><p>sem oferta nenhuma</p></article></html>")
try: rc = B.main(["--reprocess"]); res = f"rc={rc}"
except RuntimeError as e: res = f"RuntimeError: {e}"
B.recompute_gap = orig_rg; s = snap()
R["C_recompute_gap_falha"] = {"res": res, "offers": s["offers"], "igual_ao_estado_anterior": s["ids"] == base["ids"]}
# D: CLI main com STOP no meio (in-process) -> exit 3, nada muda
with_hook(4, stop_action)
rc = B.main(["--reprocess"]); B._process_snippets = orig; STOPF.unlink(missing_ok=True); s = snap()
R["D_CLI_STOP_meio"] = {"rc": rc, "ofertas_inalteradas": s["ids"] == base["ids"]}
# E: CLI STOP antes (subprocess)
STOPF.write_text("x"); r = subprocess.run([sys.executable, "-m", "preditor.backfill", "--reprocess"], cwd=tmp, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": os.environ["SRC50"]})
R["E_CLI_STOP_antes"] = {"rc": r.returncode, "out": (r.stdout + r.stderr).strip()[-60:], "ofertas_inalteradas": snap()["ids"] == base["ids"]}; STOPF.unlink()
# restaura r0 e roda sucesso real
ex("UPDATE raw_message SET content = :c WHERE url='https://x.test/r0/'", c=ART.format(b=70, d1="01/01", d2="06/01"))
out = B.main(["--reprocess"]); s = snap()
R["F_sucesso"] = {"rc": out, "offers": s["offers"]}
# G: leitor concorrente durante o reprocess ve o estado antigo (isolamento) e escritor espera
seen = []
def reader():
    time.sleep(0.5)
    for _ in range(6):
        seen.append(q("select count(*) from offer")[0][0]); time.sleep(0.4)
def slow(*a, **kw):
    time.sleep(0.6); return orig(*a, **kw)
B._process_snippets = slow
t = threading.Thread(target=reader); t.start(); B.reprocess(E); t.join(); B._process_snippets = orig
R["G_leitor_concorrente_durante_reprocess"] = {"contagens_vistas": seen, "nunca_zero_ou_parcial": all(x == base["offers"] for x in seen)}
# H: run_daily lendo durante reprocess nao ve ofertas parciais (job concorrente)
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
