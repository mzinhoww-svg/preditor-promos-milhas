import argparse, datetime as dt, json, os, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor.jobs import daily_predict as J, feed_listener as F
from preditor import collector as C, backfill as B, stop as ST
E = create_engine(os.environ["DATABASE_URL"]); R = {}
UTC = dt.UTC; D = dt.date
tmp = Path(tempfile.mkdtemp()); os.chdir(tmp)
STOPF = tmp / "STOP"
time.sleep = lambda s: None
def clean():
    with E.begin() as c:
        for t in ("alert", "prediction", "offer_evidence", "offer", "raw_message", "source_health"):
            try: c.execute(text(f"DELETE FROM {t}"))
            except Exception: pass
    STOPF.unlink(missing_ok=True)
def cnt(): 
    with E.connect() as c: return {t: c.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("prediction", "prediction_log", "raw_message", "offer", "offer_evidence", "alert", "source_health")}
def offer(o, d, start, bonus=80, fs=None):
    fs = fs or dt.datetime.combine(start, dt.time.min, tzinfo=UTC)
    with E.begin() as c:
        c.execute(text("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES(:o,:d,'transfer_bonus',:s,:b,false,'',:f) ON CONFLICT DO NOTHING"), dict(o=o, d=d, s=start, b=bonus, f=fs))
def seed_pairs(prefix, n_pairs, n=4):
    for p in range(n_pairs):
        for i in range(n): offer(f"{prefix}{p}_a", f"{prefix}{p}_b", D(2026, 1, 1) + dt.timedelta(days=30 * i))
def after_stop(fn):
    """roda fn; devolve (excecao, contagens no instante do STOP, contagens finais)."""
    snap = {}
    def make_stop():
        if not STOPF.exists():
            STOPF.write_text("x"); snap["at_stop"] = cnt()
    return make_stop, snap
def check(name, res, snap, final, extra=None):
    at = snap.get("at_stop")
    d = {"abortou": res, "gravou_apos_STOP": (at is not None and at != final), "no_STOP": at, "final": final}
    if extra: d.update(extra)
    R[name] = {k: v for k, v in d.items()}
# L1 run_daily: STOP no 2o grupo
clean(); seed_pairs("g", 5); make_stop, snap = after_stop(None)
orig = J.predict_proba; calls = []
def pp(*a, **k):
    calls.append(1)
    if len(calls) == 2: make_stop()
    return orig(*a, **k)
J.predict_proba = pp
try: J.run_daily(as_of="2026-06-01", engine=E); res = "NAO"
except ST.StopRequested: res = "StopRequested"
J.predict_proba = orig
fin = cnt(); R["L1_run_daily_meio"] = {"res": res, "grupos_processados": len(calls), "predicoes_no_STOP": snap["at_stop"]["prediction"], "predicoes_final": fin["prediction"], "gravou_apos_STOP": fin["prediction"] > snap["at_stop"]["prediction"] + 3 * 0}
# L2 run_backfill: STOP na 2a busca
clean(); B.STATE_PATH = tmp / "st.json"; B.STATE_PATH.unlink(missing_ok=True)
ART = "<html><article><p>A Smiles está oferecendo até 90% de bônus nas transferências de pontos da Livelo. A oferta é válida somente até amanhã (15). {}</p></article></html>"
B.fetch_robots_strict = lambda s: ("ok", "User-agent: *\nDisallow:\n")
B.fetch_cdx_candidates = lambda *a, **k: [{"url": f"https://x.test/p{i}/", "timestamp": f"2026010{i+1}120000"} for i in range(6)]
make_stop, snap = after_stop(None); n = []
def fsb(ts, u):
    n.append(u)
    if len(n) == 2: make_stop()
    return ART.format(u)
B.fetch_snapshot_backoff = fsb
args = argparse.Namespace(from_="202301", to=None, rate_limit=10.0, sources=["x.test"], database_url=os.environ["DATABASE_URL"], refresh_candidates=False, max_attempts=3, titles_only=False, page_size=500, slug_mode="either", max_fetch=None)
try: B.run_backfill(args); res = "NAO"
except ST.StopRequested: res = "StopRequested"
fin = cnt(); R["L2_run_backfill_meio"] = {"res": res, "downloads": len(n), "raw_no_STOP": snap["at_stop"]["raw_message"], "raw_final": fin["raw_message"],
                                           "estado_valido": json.loads(B.STATE_PATH.read_text()) is not None if B.STATE_PATH.exists() else "sem estado"}
# L3 reprocess: STOP no meio -> DELETE ja executado?
clean()
rows = [("x.test", f"https://x.test/r{i}/", ART.format(i)) for i in range(6)]
with E.begin() as c:
    for i, (s, u, h) in enumerate(rows):
        c.execute(text("INSERT INTO raw_message(source,url,content,content_hash,observed_at) VALUES (:s,:u,:c,:h,'2026-01-10')"), dict(s=s, u=u, c=h, h=f"h{i}"))
B.reprocess(E); full = cnt()["offer"]
make_stop, snap = after_stop(None); k = []
orig_ps = B._process_snippets
def ps(*a, **kw):
    k.append(1)
    if len(k) == 3: make_stop()
    return orig_ps(*a, **kw)
B._process_snippets = ps
try: B.reprocess(E); res = "NAO"
except ST.StopRequested: res = "StopRequested"
B._process_snippets = orig_ps
fin = cnt(); R["L3_reprocess_meio"] = {"res": res, "ofertas_antes": full, "ofertas_apos_STOP_no_meio": fin["offer"], "evidencias_apos": fin["offer_evidence"], "dado_destruido": fin["offer"] < full}
# L3b reprocess com STOP antes
STOPF.write_text("x")
try: B.reprocess(E); R["L3b_reprocess_STOP_antes"] = "NAO abortou"
except ST.StopRequested: R["L3b_reprocess_STOP_antes"] = {"abortou": True, "ofertas_intactas": cnt()["offer"] == fin["offer"]}
STOPF.unlink()
# L4 collect_archived_feed: STOP na 2a captura
clean(); FEED = lambda m: f"<?xml version='1.0'?><rss><channel><item><title>Titulo {m}</title><link>https://x.test/t{m}/</link><pubDate>Wed, 14 Oct 2026 10:00:00 +0000</pubDate></item></channel></rss>"
B.STATE_PATH = tmp / "st2.json"
B.list_feed_captures = lambda *a, **k: [{"timestamp": (dt.date(2026,1,1)+dt.timedelta(days=12*i)).strftime("%Y%m%d")+"120000", "original": "https://x.test/feed/"} for i in range(5)]
make_stop, snap = after_stop(None); m = []
def fsb2(ts, u):
    m.append(ts)
    if len(m) == 2: make_stop()
    return FEED(len(m))
B.fetch_snapshot_backoff = fsb2
try: B.collect_archived_feed(E, "x.test", "https://x.test/feed/", D(2025, 1, 1)); res = "NAO"
except ST.StopRequested: res = "StopRequested"
fin = cnt(); R["L4_archived_feed_meio"] = {"res": res, "capturas_buscadas": len(m), "raw_no_STOP": snap["at_stop"]["raw_message"], "raw_final": fin["raw_message"]}
# L5 collect_rss (collector) STOP no 2o item
clean()
FEED3 = "<?xml version='1.0'?><rss><channel>" + "".join(f"<item><title>Smiles oferece 80% de bonus da Livelo {i}</title><link>https://y.test/a{i}/</link><description>d{i}</description><pubDate>Wed, 14 Oct 2026 10:00:00 +0000</pubDate></item>" for i in range(5)) + "</channel></rss>"
class Tr:
    def fetch(self, url): return FEED3 if "robots" not in url else "User-agent: *\nDisallow:\n"
make_stop, snap = after_stop(None); q = []
orig_sr = C.store_raw
def sr(*a, **k):
    q.append(1)
    if len(q) == 2: make_stop()
    return orig_sr(*a, **k)
C.store_raw = sr
try: C.collect_rss(engine=E, source="y.test", url="https://y.test/feed/", transport=Tr()); res = "NAO"
except ST.StopRequested: res = "StopRequested"
C.store_raw = orig_sr
fin = cnt(); R["L5_collect_rss_meio"] = {"res": res, "store_raw_chamadas": len(q), "raw_no_STOP": snap["at_stop"]["raw_message"], "raw_final": fin["raw_message"]}
# L6 feed_listener.run_once: STOP durante a 2a fonte (dentro do loop de itens)
clean()
def rss(items): return "<?xml version='1.0'?><rss><channel>" + "".join(f"<item><title>{t}</title><link>{l}</link><pubDate>Wed, 14 Oct 2026 10:00:00 +0000</pubDate></item>" for t, l in items) + "</channel></rss>"
ART2 = lambda t: f"<html><article><p>A Smiles está oferecendo até 90% de bônus nas transferências de pontos da Livelo. A oferta é válida somente até amanhã (15). {t}</p></article></html>"
srcs = [{"source": "pontospravoar.com", "feed": "https://pontospravoar.com/feed/", "mode": "titles"},
        {"source": "passageirodeprimeira.com", "feed": "https://passageirodeprimeira.com/feed/", "mode": "article"},
        {"source": "www.melhorescartoes.com.br", "feed": "https://www.melhorescartoes.com.br/feed", "mode": "article"}]
routes = {"https://pontospravoar.com/robots.txt": (200, ""), "https://passageirodeprimeira.com/robots.txt": (200, ""), "https://www.melhorescartoes.com.br/robots.txt": (200, ""),
          "https://pontospravoar.com/feed/": (200, rss([(f"t{i}", f"https://pontospravoar.com/a{i}/") for i in range(2)])),
          "https://passageirodeprimeira.com/feed/": (200, rss([(f"p{i}", f"https://passageirodeprimeira.com/p{i}/") for i in range(5)])),
          "https://www.melhorescartoes.com.br/feed": (200, rss([("m0", "https://www.melhorescartoes.com.br/m0/")]))}
for i in range(5): routes[f"https://passageirodeprimeira.com/p{i}/"] = (200, ART2(f"p{i}"))
routes["https://www.melhorescartoes.com.br/m0/"] = (200, ART2("m0"))
make_stop, snap = after_stop(None); log = []
def get(u):
    log.append(u)
    if u.endswith("/p1/"): make_stop()   # STOP durante o 2o artigo da 2a fonte
    return routes.get(u, (404, ""))
try: out = F.run_once(E, srcs, http_get=get, sleep=lambda s: None, now=dt.datetime(2026, 10, 14, 12, tzinfo=UTC), run_pipeline=False, state_path=tmp / "ls.json"); res = "NAO"
except ST.StopRequested: res = "StopRequested"
fin = cnt()
R["L6_run_once_meio"] = {"res": res, "requisicoes_apos_STOP": len(log) - (log.index("https://passageirodeprimeira.com/p1/") + 1), "mc_visitado": any("melhorescartoes" in u for u in log),
                         "raw_no_STOP": snap["at_stop"]["raw_message"], "raw_final": fin["raw_message"], "estado_salvo": (tmp / "ls.json").exists()}
# L7 CLIs: exit codes com STOP presente
STOPF.write_text("x")
import subprocess
env = {**os.environ, "PYTHONPATH": os.environ["SRC50"]}
codes = {}
for name, argv in {"backfill": ["-m", "preditor.backfill", "--from", "202301"], "backfill_reprocess": ["-m", "preditor.backfill", "--reprocess"],
                   "feed_listener": ["-m", "preditor.jobs.feed_listener", "--once"], "daily": ["-m", "preditor.jobs.daily_predict", "daily"]}.items():
    r = subprocess.run([sys.executable, *argv], cwd=tmp, capture_output=True, text=True, env=env); codes[name] = (r.returncode, (r.stdout + r.stderr).strip()[-60:])
R["L7_CLIs_exit_com_STOP"] = codes
STOPF.unlink()
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
