import json, os, sys, tempfile, datetime as dt
from pathlib import Path
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor.jobs import feed_listener as F
E = create_engine(os.environ["DATABASE_URL"]); R = {}
NOW = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.UTC)
TMP = Path(tempfile.mkdtemp())
def wipe():
    with E.begin() as c:
        for t in ("offer_evidence", "offer", "raw_message", "source_health"):
            try: c.execute(text(f"DELETE FROM {t}"))
            except Exception: pass
def rss(items): return "<?xml version='1.0'?><rss><channel>" + "".join(f"<item><title>{t}</title><link>{l}</link><pubDate>{p}</pubDate></item>" for t, l, p in items) + "</channel></rss>"
PUB = "Wed, 14 Oct 2026 10:00:00 +0000"
ART = lambda t: f"<html><body><article><p>A Smiles está oferecendo até 90% de bônus nas transferências de pontos da Livelo. A oferta é válida somente até amanhã (15). {t}</p></article></body></html>"
ROBOTS = (200, "User-agent: *\nDisallow:\n")
class Net:
    def __init__(s, routes): s.routes = routes; s.log = []
    def get(s, url):
        s.log.append(url); v = s.routes.get(url)
        return v if v is not None else (404, "")
SRC1 = [{"source": "passageirodeprimeira.com", "feed": "https://passageirodeprimeira.com/feed/", "mode": "article"}]
SL = []
def run(routes, sources=SRC1, now=NOW, state="s.json"):
    SL.clear(); n = Net(routes)
    out = F.run_once(E, sources, http_get=n.get, sleep=SL.append, now=now, run_pipeline=False, state_path=TMP / state)
    return out, n
def routes(items, **kw):
    r = {"https://passageirodeprimeira.com/robots.txt": ROBOTS, "https://passageirodeprimeira.com/feed/": (200, rss(items))}
    for t, l, p in items: r[l] = (200, ART(t))
    r.update(kw); return r
def raws():
    with E.connect() as c: return [r[0] for r in c.execute(text("SELECT url FROM raw_message ORDER BY id"))]
# ---- URL canonica
wipe()
with E.begin() as c:
    c.execute(text("INSERT INTO raw_message(source,url,content,content_hash,observed_at) VALUES ('passageirodeprimeira.com','http://www.passageirodeprimeira.com/Artigo-A/?utm_source=x#frag','c1','h1',now())"))
items = [("A", "https://passageirodeprimeira.com/artigo-a/", PUB), ("B", "https://passageirodeprimeira.com/artigo-b/?utm_campaign=z", PUB), ("C", "http://passageirodeprimeira.com/artigo-c", PUB)]
out, n = run(routes(items)); 
R["U1_canonica_conhecidos"] = {"novos": out["passageirodeprimeira.com"]["items_new"], "buscou_A": any("artigo-a" in u for u in n.log), "gravadas": raws()}
out2, n2 = run(routes([("B", "https://passageirodeprimeira.com/artigo-b/", PUB), ("C", "https://www.passageirodeprimeira.com/artigo-c/?x=1", PUB)]), state="s2.json")
R["U2_variantes_nao_duplicam"] = {"novos": out2["passageirodeprimeira.com"]["items_new"], "total_raw": len(raws())}
# links com query como identificador (?p=ID)
wipe(); items = [("P1", "https://passageirodeprimeira.com/?p=101", PUB), ("P2", "https://passageirodeprimeira.com/?p=102", PUB), ("P3", "https://passageirodeprimeira.com/?p=103", PUB)]
out, n = run(routes(items), state="s3.json")
R["U3_links_com_query_p=ID"] = {"novos": out["passageirodeprimeira.com"]["items_new"], "gravadas": raws()}
# caixa: dois artigos distintos so por caixa no path
wipe(); items = [("X1", "https://passageirodeprimeira.com/Promo-ABC/", PUB), ("X2", "https://passageirodeprimeira.com/promo-abc/", PUB)]
out, n = run(routes(items), state="s4.json"); R["U4_caixa_distinta"] = {"novos": out["passageirodeprimeira.com"]["items_new"], "gravadas": raws()}
# ---- teto diario
wipe(); st = TMP / "cap.json"; st.write_text(json.dumps({"passageirodeprimeira.com": {"day": "2026-10-14", "count": 198}}))
items = [(f"T{i}", f"https://passageirodeprimeira.com/t{i}/", PUB) for i in range(6)]
out, n = run(routes(items), state="cap.json")
R["D1_teto_198_de_200"] = {"status": out["passageirodeprimeira.com"]["status"], "req": len(n.log), "novos": out["passageirodeprimeira.com"]["items_new"], "state": json.loads(st.read_text())}
with E.connect() as c: R["D1_health_registrado"] = c.execute(text("SELECT count(*), bool_or(alert) FROM source_health WHERE source='passageirodeprimeira.com'")).first()._mapping.items().__len__()
out, n = run(routes(items), state="cap.json"); R["D2_mesmo_dia_apos_teto"] = {"status": out["passageirodeprimeira.com"]["status"], "req": len(n.log)}
out, n = run(routes(items), now=NOW + dt.timedelta(days=1), state="cap.json"); R["D3_dia_seguinte_reseta"] = {"status": out["passageirodeprimeira.com"]["status"], "req": len(n.log), "novos": out["passageirodeprimeira.com"]["items_new"]}
# ---- pausa apos 429/503
wipe(); (TMP / "p.json").write_text("{}")
items = [(f"Q{i}", f"https://passageirodeprimeira.com/q{i}/", PUB) for i in range(4)]
r = routes(items); r["https://passageirodeprimeira.com/q1/"] = (429, "")
out, n = run(r, state="p.json")
R["P1_429_no_artigo"] = {"status": out["passageirodeprimeira.com"], "req": len(n.log), "gravadas": len(raws()), "pause_until": json.loads((TMP / "p.json").read_text()).get("passageirodeprimeira.com", {}).get("pause_until")}
out, n = run(routes(items), now=NOW + dt.timedelta(minutes=30), state="p.json"); R["P2_30min_depois"] = {"status": out["passageirodeprimeira.com"]["status"], "req": len(n.log)}
out, n = run(routes(items), now=NOW + dt.timedelta(minutes=61), state="p.json"); R["P3_61min_depois"] = {"status": out["passageirodeprimeira.com"]["status"], "req": len(n.log), "novos": out["passageirodeprimeira.com"]["items_new"]}
wipe(); r = routes(items); r["https://passageirodeprimeira.com/robots.txt"] = (503, ""); (TMP / "p2.json").write_text("{}")
out, n = run(r, state="p2.json"); R["P4_503_no_robots"] = {"status": out["passageirodeprimeira.com"]["status"], "req": len(n.log)}
out, n = run(routes(items), now=NOW + dt.timedelta(minutes=10), state="p2.json"); R["P5_10min_depois_pausada"] = {"status": out["passageirodeprimeira.com"]["status"], "req": len(n.log)}
with E.connect() as c: R["P5_health_durante_pausa"] = c.execute(text("SELECT count(*) FROM source_health")).scalar()
# 429 no feed
wipe(); r = routes(items); r["https://passageirodeprimeira.com/feed/"] = (429, ""); (TMP / "p3.json").write_text("{}")
out, n = run(r, state="p3.json"); R["P6_429_no_feed"] = {"status": out["passageirodeprimeira.com"]["status"], "pause_gravada": "pause_until" in json.loads((TMP / "p3.json").read_text()).get("passageirodeprimeira.com", {})}
# ---- estado corrompido / perdido
(TMP / "bad.json").write_text("{nao e json"); wipe()
out, n = run(routes(items), state="bad.json"); R["S1_estado_corrompido"] = {"status": out["passageirodeprimeira.com"]["status"], "req": len(n.log), "reescreveu": (TMP / "bad.json").read_text()[:40]}
# estado so gravado no fim: excecao no meio perde contagem
wipe(); (TMP / "crash.json").write_text("{}")
orig = F._store
def boom(*a, **k): raise RuntimeError("crash")
F._store = boom
try: run(routes(items), state="crash.json")
except Exception as e: R["S2_crash_meio"] = {"exc": type(e).__name__, "estado_gravado": (TMP / "crash.json").read_text()}
F._store = orig
# ---- X4/pacing herdados
wipe()
srcs = [{"source": "pontospravoar.com", "feed": "https://pontospravoar.com/feed/", "mode": "titles"}, SRC1[0],
        {"source": "www.melhorescartoes.com.br", "feed": "https://www.melhorescartoes.com.br/feed", "mode": "article"}]
rr = routes([("Z", "https://passageirodeprimeira.com/z/", PUB)])
rr.update({"https://pontospravoar.com/robots.txt": ROBOTS, "https://pontospravoar.com/feed/": (200, rss([("t", "https://pontospravoar.com/a/", PUB)])),
           "https://www.melhorescartoes.com.br/robots.txt": ROBOTS, "https://www.melhorescartoes.com.br/feed": (200, rss([("m", "https://www.melhorescartoes.com.br/m/", PUB)])),
           "https://www.melhorescartoes.com.br/m/": (200, ART("m"))})
def boom2(engine, source, *a, **k):
    if source.startswith("passageiro"): raise RuntimeError("falha interna simulada")
    return orig(engine, source, *a, **k)
F._store = boom2
try:
    out, n = run(rr, sources=srcs, state="x4.json"); R["X4_excecao_interna"] = {k: v["status"] for k, v in out.items()}
except Exception as e:
    R["X4_excecao_interna"] = f"EXC {type(e).__name__}: {e} -> aborta o ciclo; MC visitado={any('melhorescartoes' in u for u in n.log)}"
F._store = orig
# pacing entre execucoes: duas execucoes seguidas sem espera
wipe(); (TMP / "pc.json").write_text("{}")
SL.clear(); out, n = run(routes([("W", "https://passageirodeprimeira.com/w/", PUB)]), state="pc.json")
R["PC_primeira_requisicao_sem_espera"] = {"sleeps_1a_exec": list(SL), "req": len(n.log)}
# ---- robots_changed na API
os.environ["PREDITOR_API_KEY"] = "k"
from fastapi.testclient import TestClient
from preditor.api import create_app
def rc(hashes):
    with E.begin() as c:
        c.execute(text("DELETE FROM source_health"))
        for i, h in enumerate(hashes):  # hashes em ordem do mais antigo ao mais novo
            c.execute(text("INSERT INTO source_health(source,checked_at,items_new,extraction_rate,alert,robots_hash) VALUES ('fonte_r',:t,1,0.5,false,:h)"), {"t": dt.datetime.now(dt.UTC) - dt.timedelta(hours=len(hashes) - i), "h": h})
    with TestClient(create_app()) as cl:
        s = [x for x in cl.get("/v1/source-health", headers={"X-API-Key": "k"}).json()["sources"] if x["source"] == "fonte_r"][0]
    return s["robots_changed"]
R["RC"] = {"h0,h0": rc(["h0", "h0"]), "h0,h1 (acabou de mudar)": rc(["h0", "h1"]), "h0,h1,h1 (1 check depois)": rc(["h0", "h1", "h1"]),
           "h0,h1,h1,h1": rc(["h0", "h1", "h1", "h1"]), "h0,None,h1": rc(["h0", None, "h1"])}
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
