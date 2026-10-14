import argparse, json, os, sys, tempfile, time, datetime as dt
from pathlib import Path
sys.path.insert(0, "src")
from preditor import backfill as B, collector as C
from sqlalchemy import create_engine, text
E = create_engine(os.environ["DATABASE_URL"]); R = {}
SL = []; time.sleep = lambda s: SL.append(s)
RAW = Path(os.environ["RAWDIR"])
def wipe():
    with E.begin() as c:
        for t in ("offer_evidence", "offer", "raw_message"): c.execute(text(f"DELETE FROM {t}"))
def cnt():
    with E.connect() as c: return {t: c.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("raw_message", "offer", "offer_evidence")}
def args(**k):
    d = dict(from_="202301", to=None, rate_limit=10.0, sources=["fonte-a.test"], database_url=os.environ["DATABASE_URL"], refresh_candidates=False,
             max_attempts=3, titles_only=False, page_size=500, slug_mode="either"); d.update(k); return argparse.Namespace(**d)
FETCH = []
def setup(urls, robots=("ok", "User-agent: *\nDisallow:\n"), fail=(), pages=None):
    tmp = tempfile.mkdtemp(); os.chdir(tmp); B.STATE_PATH = Path(tmp) / "state.json"; SL.clear(); FETCH.clear()
    B.fetch_cdx_candidates = lambda s, f, t, rl, ps, sm="either": [{"url": u, "timestamp": f"2024031{i%9}120000"} for i, u in enumerate(urls)]
    B.fetch_robots_strict = lambda s: robots
    def fs(ts, url):
        FETCH.append((url, len(SL)))
        if url in fail: return None
        if pages and url in pages: return pages[url]
        return (RAW / "86.html").read_text() + f"<!-- {url} -->"
    B.fetch_snapshot_backoff = fs
U = [f"https://fonte-a.test/p{i}/" for i in range(5)]
# robots indisponivel/disallow total -> zero fetch
wipe(); setup(U, robots=("robots_unavailable", None)); B.run_backfill(args()); R["R1_robots_indisponivel_fetches"] = len(FETCH)
wipe(); setup(U, robots=("ok", "User-agent: *\nDisallow: /\n")); B.run_backfill(args()); R["R2_disallow_total_fetches"] = len(FETCH)
wipe(); setup(U, robots=("ok", "User-agent: *\nDisallow: /p3/\n")); B.run_backfill(args())
st = json.loads(B.STATE_PATH.read_text())["sources"]["fonte-a.test"]["processed"]
R["R3_disallow_url_p3"] = {"baixou_p3": any(u.endswith("/p3/") for u, _ in FETCH), "status_p3": st[U[3]]["status"], "fetches": len(FETCH)}
# ritmo e idempotencia
wipe(); setup(U); B.run_backfill(args())
R["P1_sleep10_antes_de_cada_fetch"] = all(i >= 1 and SL[i-1] == 10.0 for _, i in FETCH)
c1 = cnt(); n = len(FETCH); B.run_backfill(args()); R["I1_reexec"] = {"fetches_novos": len(FETCH)-n, "antes": c1, "depois": cnt()}
B.STATE_PATH.unlink(); B.run_backfill(args()); R["I2_sem_state"] = cnt()
with E.connect() as c: R["G_gap_flags"] = [tuple(r) for r in c.execute(text("SELECT published_at IS NOT NULL, published_vs_capture_gap FROM raw_message LIMIT 3"))]
# tentativas
wipe(); setup(U, fail=(U[1],))
for _ in range(5): B.run_backfill(args(max_attempts=3))
R["T1_fetch_failed_tentativas(max3)"] = sum(1 for u, _ in FETCH if u == U[1])
# status error limitado?
wipe(); setup(U[:2]); orig = B.ingest_page
B.ingest_page = lambda *a, **k: (_ for _ in ()).throw(ValueError("x"))
for _ in range(6): B.run_backfill(args(max_attempts=3))
R["T2_error_fetches_6exec(max3)"] = sum(1 for u, _ in FETCH if u == U[0]); B.ingest_page = orig
# backoff 429/503
class Resp:
    def __init__(s, c, t="ok"): s.status_code = c; s.text = t
class Cli:
    seq = []
    def __init__(s): pass
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def get(s, url): return Cli.seq.pop(0)
B._new_client = lambda: Cli()
SL.clear(); Cli.seq = [Resp(429), Resp(429), Resp(200, "HTML")]; r = B.fetch_snapshot_backoff.__wrapped__("2024","u") if hasattr(B.fetch_snapshot_backoff, "__wrapped__") else None
import importlib; importlib.reload(B); B._new_client = lambda: Cli(); time.sleep = lambda s: SL.append(s)
SL.clear(); Cli.seq = [Resp(429), Resp(429), Resp(200, "HTML")]; R["BK1_429_429_200"] = (B.fetch_snapshot_backoff("2024", "u"), list(SL))
SL.clear(); Cli.seq = [Resp(429), Resp(429), Resp(429)]; R["BK2_429x3"] = (B.fetch_snapshot_backoff("2024", "u"), list(SL))
SL.clear(); Cli.seq = [Resp(404)]; R["BK3_404"] = (B.fetch_snapshot_backoff("2024", "u"), list(SL))
# prorrogacao dedupe + reprocess no banco proprio
wipe()
with E.begin() as c:
    for fim, seg, lab in (("2026-03-20", False, ""), ("2026-03-31", True, "clube")):
        c.execute(text("INSERT INTO offer(origin,destination,event_type,start_at,end_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES('livelo','smiles','transfer_bonus','2026-03-19',:f,80,:g,:l,now())"), {"f": fim, "g": seg, "l": lab})
R["D1_prorrogacao_mescladas"] = B.dedupe_extensions(E)
with E.connect() as c: R["D1_apos"] = [tuple(map(str, r)) for r in c.execute(text("SELECT start_at,end_at,bonus_pct FROM offer"))]
print(json.dumps(R, indent=1, default=str))
