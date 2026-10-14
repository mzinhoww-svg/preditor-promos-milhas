"""QA PR #36 — ataques ao backfill (stubs de rede; banco proprio qa_backfill). Nao altera o codigo do autor."""
import argparse, json, os, sys, tempfile, time, types
from pathlib import Path
sys.path.insert(0, "src")
from preditor import backfill as B
from preditor import collector as C
from sqlalchemy import create_engine, text
E = create_engine(os.environ["DATABASE_URL"])
R = {}
SLEEPS, FETCHES, ROBOTS_CALLS = [], [], []
real_sleep = time.sleep
time.sleep = lambda s: SLEEPS.append(("sleep", s))
HTML = "<html><head><title>Smiles oferece até 80% de bônus na transferência da Livelo</title><meta property='article:published_time' content='@@TS@@'></head><body><p>A Smiles está oferecendo até 80% de bônus nas transferências de pontos da Livelo de 10/03/2024 a 20/03/2024.</p></body></html>"
def wipe():
    with E.begin() as c:
        for t in ("offer_evidence","offer","raw_message"):
            c.execute(text(f"DELETE FROM {t}"))
def counts():
    with E.connect() as c:
        return {t: c.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("raw_message","offer","offer_evidence")}
def args(**kw):
    d = dict(from_="202301", to=None, rate_limit=10.0, sources=["fonte-a.test"], database_url=os.environ["DATABASE_URL"],
             refresh_candidates=False, max_attempts=3, titles_only=False, page_size=500)
    d.update(kw); return argparse.Namespace(**d)
def setup(tmp, urls, robots="User-agent: *\nDisallow:\n", fail=(), robots_raises=False, bodies=None):
    os.chdir(tmp); B.STATE_PATH = Path(tmp) / "state.json"
    if B.STATE_PATH.exists(): B.STATE_PATH.unlink()
    SLEEPS.clear(); FETCHES.clear(); ROBOTS_CALLS.clear()
    B.fetch_cdx_candidates = lambda source, f, t, rl, ps: [{"url": u, "timestamp": f"2024031{i%9}120000"} for i, u in enumerate(urls)]
    def fr(source, transport=None, rate_limiter=None):
        ROBOTS_CALLS.append(source)
        if robots_raises: raise OSError("boom")
        return robots
    C.fetch_robots = fr
    def fs(ts, url, transport=None):
        FETCHES.append((url, len(SLEEPS)))
        if url in fail: return None
        if bodies and url in bodies: return bodies[url]
        base = open("<scratchpad>/qa7/raw/118.html").read() if (len(FETCHES) % 2) else open("<scratchpad>/qa7/raw/86.html").read()
        return base + f"<!-- {url} -->"
    C.fetch_snapshot = fs
U = [f"https://fonte-a.test/p{i}/" for i in range(6)]
tmp = tempfile.mkdtemp()
# A1 robots Disallow: / -> aborta sem baixar
wipe(); setup(tmp, U, robots="User-agent: *\nDisallow: /\n")
try: B.run_backfill(args()); R["A1_robots_disallow_all"] = "NAO abortou"
except SystemExit as e: R["A1_robots_disallow_all"] = f"abortou: {str(e)[:60]}; fetches={len(FETCHES)}"
# A2 robots Disallow de um caminho especifico (/p3/) -> URL proibida e baixada?
wipe(); setup(tmp, U, robots="User-agent: *\nDisallow: /p3/\n")
B.run_backfill(args())
R["A2_disallow_/p3/_url_proibida_baixada"] = any(u.endswith("/p3/") for u, _ in FETCHES)
# A3 robots indisponivel (fetch devolve None) -> segue (fail-open)?
wipe(); setup(tmp, U, robots=None)
B.run_backfill(args()); R["A3_robots_None_baixou"] = len(FETCHES)
# A3b robots lanca excecao
wipe(); setup(tmp, U, robots_raises=True)
B.run_backfill(args()); R["A3b_robots_excecao_baixou"] = len(FETCHES)
# A4 ritmo: sleep(10) imediatamente antes de cada fetch
wipe(); setup(tmp, U)
B.run_backfill(args())
ok = all(i >= 1 and SLEEPS[i-1] == ("sleep", 10.0) for _, i in FETCHES)
R["A4_sleep10_antes_de_cada_fetch"] = (ok, len(FETCHES))
R["A4_rate_limit_0_aceito"] = None
# A5 idempotencia: 2a execucao nao baixa nem duplica
c1 = counts(); n1 = len(FETCHES); B.run_backfill(args()); R["A5_reexec"] = {"fetches_novos": len(FETCHES)-n1, "antes": c1, "depois": counts()}
# A5b apaga state (perda) e reexecuta: store_raw dedupe por content_hash?
B.STATE_PATH.unlink(); B.run_backfill(args()); R["A5b_sem_state_reexec"] = {"depois": counts()}
# A6 retomada: interrompe no 4o fetch
wipe(); setup(tmp, U)
orig = C.fetch_snapshot
def boom(ts, url, transport=None):
    if len(FETCHES) >= 3: raise KeyboardInterrupt()
    return orig(ts, url, transport)
C.fetch_snapshot = boom
try: B.run_backfill(args())
except KeyboardInterrupt: pass
st = json.loads(B.STATE_PATH.read_text()); done = sum(v["status"]=="done" for v in st["sources"]["fonte-a.test"]["processed"].values())
C.fetch_snapshot = orig; n = len(FETCHES); B.run_backfill(args())
R["A6_retomada"] = {"done_antes": done, "fetches_na_retomada": len(FETCHES)-n, "final": counts()}
# A7 falha permanente: tentativas por execucao e limite
wipe(); setup(tmp, U, fail=(U[1],))
for _ in range(4): B.run_backfill(args(max_attempts=2))
R["A7_tentativas_url_falha"] = sum(1 for u, _ in FETCHES if u == U[1])
# A8 status 'error' (excecao no processamento) e re-tentado sem limite?
wipe(); setup(tmp, U[:2])
orig_pm = C.process_raw_message
def pm(*a, **k): raise ValueError("falha de extracao")
C.process_raw_message = pm
for _ in range(5): B.run_backfill(args(max_attempts=2))
R["A8_error_refetch_por_exec"] = sum(1 for u, _ in FETCHES if u == U[0])
C.process_raw_message = orig_pm
# A9 entrada vazia / conteudo vazio / datas conflitantes
wipe(); setup(tmp, [], robots="")
B.run_backfill(args()); R["A9_sem_candidatos"] = {"fetches": len(FETCHES), **counts()}
wipe(); setup(tmp, U[:2], bodies={U[0]: ""})
B.run_backfill(args()); R["A9b_conteudo_vazio"] = {"estado": [v["status"] for v in json.loads(B.STATE_PATH.read_text())["sources"]["fonte-a.test"]["processed"].values()], **counts()}
wipe(); setup(tmp, U[:1], bodies={U[0]: HTML.replace("@@TS@@","2031-01-01T00:00:00+00:00")})
B.run_backfill(args())
with E.connect() as c: R["A9c_published_futuro_first_seen"] = [str(r[0]) for r in c.execute(text("SELECT first_seen_at FROM offer"))] + [str(r[0]) for r in c.execute(text("SELECT observed_at FROM raw_message"))]
# A10 URLs duplicadas nos candidatos
wipe(); setup(tmp, [U[0], U[0], U[0]])
B.run_backfill(args()); R["A10_urls_duplicadas"] = {"fetches": len(FETCHES), **counts()}
print(json.dumps(R, indent=1, default=str))
