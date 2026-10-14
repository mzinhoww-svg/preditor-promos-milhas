import json, os, sys, datetime as dt
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor.jobs import feed_listener as F
E = create_engine(os.environ["DATABASE_URL"]); R = {}
NOW = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.UTC)
def wipe():
    with E.begin() as c:
        for t in ("offer_evidence", "offer", "raw_message", "source_health"):
            try: c.execute(text(f"DELETE FROM {t}"))
            except Exception as e: pass
def rss(items): return "<?xml version='1.0'?><rss><channel>" + "".join(
    f"<item><title>{t}</title><link>{l}</link><pubDate>{p}</pubDate><description>CORPO_PPV_PROIBIDO {t}</description></item>" for t, l, p in items) + "</channel></rss>"
PUB = "Wed, 14 Oct 2026 10:00:00 +0000"; OLD = "Mon, 01 Sep 2026 10:00:00 +0000"
ART = lambda t: f"<html><body><article><p>A Smiles está oferecendo até 90% de bônus nas transferências de pontos da Livelo. A oferta é válida somente até amanhã (15). {t}</p></article></body></html>"
class Net:
    def __init__(s, routes): s.routes = routes; s.log = []
    def get(s, url):
        s.log.append(url)
        v = s.routes.get(url)
        if isinstance(v, Exception): return (0, "")  # _http_get real captura erros de rede e devolve (0, '')
        return v if v is not None else (404, "")
SL = []
def sleeper(x): SL.append(x)
OK_ROBOTS = (200, "User-agent: *\nDisallow:\n")
SRC = [{"source": "pontospravoar.com", "feed": "https://pontospravoar.com/feed/", "mode": "titles"},
       {"source": "passageirodeprimeira.com", "feed": "https://passageirodeprimeira.com/feed/", "mode": "article"},
       {"source": "www.melhorescartoes.com.br", "feed": "https://www.melhorescartoes.com.br/feed", "mode": "article"}]
def routes(**kw):
    r = {"https://pontospravoar.com/robots.txt": OK_ROBOTS, "https://passageirodeprimeira.com/robots.txt": OK_ROBOTS, "https://www.melhorescartoes.com.br/robots.txt": OK_ROBOTS,
         "https://pontospravoar.com/feed/": (200, rss([("Smiles oferece até 80% de bônus da Livelo hoje", "https://pontospravoar.com/a1/", PUB), ("Outra notícia", "https://pontospravoar.com/a2/", PUB)])),
         "https://passageirodeprimeira.com/feed/": (200, rss([("Art 1", "https://passageirodeprimeira.com/p1/", PUB), ("Art 2", "https://passageirodeprimeira.com/p2/", OLD)])),
         "https://www.melhorescartoes.com.br/feed": (200, rss([("Art MC", "https://www.melhorescartoes.com.br/m1.html", PUB)])),
         "https://passageirodeprimeira.com/p1/": (200, ART("p1")), "https://passageirodeprimeira.com/p2/": (200, ART("p2")),
         "https://www.melhorescartoes.com.br/m1.html": (200, ART("m1"))}
    r.update(kw); return r
def run(rt, sources=SRC, **kw):
    SL.clear(); n = Net(rt)
    out = F.run_once(E, sources, http_get=n.get, sleep=sleeper, now=NOW, run_pipeline=False, **kw)
    return out, n
def cnt():
    with E.connect() as c:
        return {"raw": c.execute(text("SELECT count(*) FROM raw_message")).scalar(), "offer": c.execute(text("SELECT count(*) FROM offer")).scalar(),
                "health": c.execute(text("SELECT count(*) FROM source_health")).scalar()}
# 1 execucao normal
wipe(); out, n = run(routes())
R["N1_status"] = {k: (v["status"], v.get("items_new"), v.get("offers")) for k, v in out.items()}; R["N1_counts"] = cnt()
with E.connect() as c:
    R["N1_ppv_corpo"] = {"max_len": c.execute(text("SELECT max(length(content)) FROM raw_message WHERE source LIKE 'pontospravoar%'")).scalar(),
                         "tem_corpo": c.execute(text("SELECT count(*) FROM raw_message WHERE content ILIKE '%CORPO_PPV_PROIBIDO%'")).scalar()}
    R["N1_gap"] = [tuple(map(str, r)) for r in c.execute(text("SELECT url, published_vs_capture_gap, observed_at::date FROM raw_message WHERE source LIKE 'passage%' ORDER BY url"))]
R["N1_requests_ppv_corpo"] = [u for u in n.log if u.startswith("https://pontospravoar.com/a")]
# 2 ritmo: sleeps por dominio
wipe(); out, n = run(routes())
R["P1_sleeps"] = {"n_requests": len(n.log), "n_sleeps": len(SL), "todos_10": all(s == 10.0 for s in SL)}
dom = {}
for u in n.log: dom.setdefault(u.split("/")[2], 0); dom[u.split("/")[2]] += 1
R["P1_req_por_dominio"] = dom; R["P1_sleeps_esperados"] = sum(max(c - 1, 0) for c in dom.values())
# 3 idempotencia
c1 = cnt(); out2, n2 = run(routes())
R["I1_reexec"] = {"novos": {k: v.get("items_new") for k, v in out2.items()}, "fetch_artigos": [u for u in n2.log if "/p" in u and u.endswith("/") and "feed" not in u], "antes": c1, "depois": cnt()}
# 4 robots indisponivel / disallow por URL / disallow do feed
wipe(); out, n = run(routes(**{"https://passageirodeprimeira.com/robots.txt": (403, "")}))
R["F1_robots_403"] = {"status_pdp": out["passageirodeprimeira.com"]["status"], "outras": {k: v["status"] for k, v in out.items() if k != "passageirodeprimeira.com"},
                      "fetch_feed_pdp": any(u == "https://passageirodeprimeira.com/feed/" for u in n.log), "counts": cnt()}
with E.connect() as c: R["F1_health"] = [tuple(map(str, r)) for r in c.execute(text("SELECT source, alert, items_new FROM source_health ORDER BY source"))]
wipe(); out, n = run(routes(**{"https://passageirodeprimeira.com/robots.txt": (200, "User-agent: *\nDisallow: /p2/\n")}))
R["F2_disallow_url_p2"] = {"baixou_p2": "https://passageirodeprimeira.com/p2/" in n.log, "baixou_p1": "https://passageirodeprimeira.com/p1/" in n.log, "status": out["passageirodeprimeira.com"]["status"]}
wipe(); out, n = run(routes(**{"https://passageirodeprimeira.com/robots.txt": (200, "User-agent: *\nDisallow: /feed/\n")}))
R["F3_disallow_feed"] = {"status": out["passageirodeprimeira.com"]["status"], "fetch_feed": "https://passageirodeprimeira.com/feed/" in n.log, "outras_ok": all(v["status"] == "ok" for k, v in out.items() if k != "passageirodeprimeira.com")}
wipe(); out, n = run(routes(**{"https://passageirodeprimeira.com/robots.txt": (404, "")}))
R["F4_robots_404"] = out["passageirodeprimeira.com"]["status"]
# 5 falha de fonte nao derruba as outras
wipe(); out, n = run(routes(**{"https://passageirodeprimeira.com/feed/": (500, ""), "https://www.melhorescartoes.com.br/feed": OSError("conexao")}))
R["X1_feed_500_e_excecao"] = {k: v["status"] for k, v in out.items()}
R["X1_excecao_nao_tratada"] = None
wipe()
try:
    out, n = run(routes(**{"https://www.melhorescartoes.com.br/robots.txt": OSError("dns")}))
    R["X2_excecao_em_http_get_robots"] = {k: v["status"] for k, v in out.items()}
except Exception as e:
    R["X2_excecao_em_http_get_robots"] = f"EXC {type(e).__name__}: {e} (derruba as outras)"
wipe(); bad = routes(**{"https://passageirodeprimeira.com/feed/": (200, "<rss><channel><item><title>x</title><link>https://passageirodeprimeira.com/p1/</link>")})
try:
    out, n = run(bad); R["X3_xml_quebrado"] = {k: v["status"] for k, v in out.items()}
except Exception as e: R["X3_xml_quebrado"] = f"EXC {type(e).__name__}: {e}"
# 6 artigo 404 em uma fonte article: falha parcial e total
wipe(); out, n = run(routes(**{"https://passageirodeprimeira.com/p1/": (404, ""), "https://passageirodeprimeira.com/p2/": (404, "")}))
R["A1_todos_artigos_404"] = out["passageirodeprimeira.com"]
with E.connect() as c: R["A1_health"] = [tuple(map(str, r)) for r in c.execute(text("SELECT source, alert, items_new FROM source_health WHERE source LIKE 'passage%'"))]
# 7 retomada: 2a rodada apos falha pega os itens que falharam
out2, n2 = run(routes()); R["A2_retomada"] = {"items_new": out2["passageirodeprimeira.com"]["items_new"], "falhas": out2["passageirodeprimeira.com"].get("failures")}
# 8 feed vazio / item sem link / titulo duplicado
wipe(); out, n = run(routes(**{"https://pontospravoar.com/feed/": (200, rss([]))}))
R["E1_feed_vazio"] = out["pontospravoar.com"]
wipe(); out, n = run(routes(**{"https://pontospravoar.com/feed/": (200, rss([("Mesmo titulo", "https://pontospravoar.com/d1/", PUB), ("Mesmo titulo", "https://pontospravoar.com/d2/", PUB)]))}))
R["E2_titulo_duplicado_items_new"] = out["pontospravoar.com"]["items_new"]; R["E2_raw"] = cnt()["raw"]
# 8b excecao interna (ex.: erro de banco/extracao) em uma fonte derruba as outras?
wipe(); orig_store = F._store
def boom(engine, source, *a, **k):
    if source.startswith("passageirodeprimeira"): raise RuntimeError("falha interna simulada")
    return orig_store(engine, source, *a, **k)
F._store = boom
try:
    out, n = run(routes()); R["X4_excecao_interna_pdp"] = {k: v["status"] for k, v in out.items()}
except Exception as e:
    R["X4_excecao_interna_pdp"] = f"EXC {type(e).__name__}: {e} -> run_once abortou; melhorescartoes visitado? {any('melhorescartoes' in u for u in n.log) if 'n' in dir() else '?'}"
F._store = orig_store
with E.connect() as c: R["X4_raw_apos"] = c.execute(text("SELECT source, count(*) FROM raw_message GROUP BY 1")).all() and [tuple(r) for r in c.execute(text("SELECT source, count(*) FROM raw_message GROUP BY 1"))]
# 9 source_status / API
from preditor.jobs.feed_listener import source_status
R["S1_source_status"] = {k: {kk: str(vv) for kk, vv in v.items()} for k, v in source_status(E, NOW).items()}
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
