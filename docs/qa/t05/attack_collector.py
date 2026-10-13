import sys, os, time
sys.path.insert(0, sys.argv[1] + "/src")
import httpx
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import create_engine, text
from preditor import collector as C
def show(n, ok, d=""): print(f"[{'OK ' if ok else 'FALHA'}] {n} {d}")
eng = create_engine(os.environ["DATABASE_URL"])
def reset():
    with eng.begin() as c: c.execute(text("TRUNCATE offer_evidence, offer, raw_message, source_health RESTART IDENTITY CASCADE"))
def q(sql, **p):
    with eng.connect() as c: return c.execute(text(sql), p).fetchall()
def counts(): return {t: q(f"select count(*) from {t}")[0][0] for t in ("raw_message","offer","offer_evidence","source_health")}
def feed(items):
    return '<?xml version="1.0"?><rss><channel>' + "".join(f"<item><title>{t}</title><link>{l}</link><pubDate>{p}</pubDate><description>{d}</description></item>" for t,l,p,d in items) + "</channel></rss>"
T0 = datetime(2026,10,13,12,0,tzinfo=timezone.utc)
SRC="passageirodeprimeira.com"; URL="https://passageirodeprimeira.com/feed/"
def run(xml, **kw):
    kw.setdefault("now", T0)
    return C.collect_rss(engine=eng, source=kw.pop("source",SRC), url=URL, transport=(lambda u: xml), **kw)
# S1 caminho feliz
reset()
x=feed([("Livelo para Smiles: 90% de bônus","https://passageirodeprimeira.com/a1","Mon, 12 Oct 2026 10:00:00 GMT","Transferência de Livelo para Smiles com 90% de bônus de 15/10/2026 a 20/10/2026."),
        ("Esfera para Smiles: 80% de bônus","https://passageirodeprimeira.com/a2","Mon, 12 Oct 2026 11:00:00 GMT","Esfera para Smiles com 80% de bônus de 16/10/2026 a 21/10/2026.")])
ids=run(x); c1=counts(); print("   S1", ids, c1)
show("S1 2 itens -> 2 raw, 2 offers, 2 evidencias, 1 source_health", c1=={"raw_message":2,"offer":2,"offer_evidence":2,"source_health":1}, str(c1))
o=q("select origin,destination,event_type,start_at,end_at,bonus_pct,first_seen_at,n_sources,validated,weight from offer order by id"); print("   offers:", [tuple(map(str,r)) for r in o])
show("S1b first_seen_at = pubDate (12/10 10:00), nao a hora da coleta", o and str(o[0][6]).startswith("2026-10-12"), f"{o[0][6] if o else None}")
sh=q("select source,items_new,extraction_rate,alert from source_health"); print("   source_health:", sh)
# S2 idempotencia
ids2=run(x); c2=counts(); sh2=q("select items_new,alert from source_health order by checked_at")
show("S2 reexecucao mesmo `now`: sem linhas novas", {k:c2[k] for k in ("raw_message","offer","offer_evidence")}==c1 and True, str(c2))
print("   S2 source_health apos 2a execucao (mesmo now):", sh2, "(PK source+checked_at: 2a linha perdida em silencio)")
run(x, now=T0+timedelta(hours=1)); sh3=q("select items_new, alert from source_health order by checked_at")
show("S2b 3a execucao 1h depois sem itens novos reporta items_new=0 (alert)", sh3[-1][0]==0, f"items_new reportado={sh3[-1][0]} (conta itens do feed, nao novos)")
# S3 sem direcao
reset(); x3=feed([("Livelo e Smiles oferecem 90% de bônus","https://passageirodeprimeira.com/b1","Mon, 12 Oct 2026 10:00:00 GMT","Livelo e Smiles oferecem 90% de bônus de transferência de 15/10/2026 a 20/10/2026.")])
run(x3); c=counts(); show("S3 'Livelo e Smiles' (sem direcao) vira oferta ou erro visivel", c["offer"]==1, str(c)+" (raw gravado, oferta perdida em silencio)")
# S4 so data de fim
reset(); x4=feed([("Livelo para Smiles 50% de bônus","https://passageirodeprimeira.com/c1","Mon, 12 Oct 2026 10:00:00 GMT","Livelo para Smiles: 50% de bônus até 20/10/2026.")])
run(x4); o=q("select start_at,end_at,first_seen_at from offer"); print("   S4 offer:", o)
show("S4 so data de fim NAO inventa start_at (= first_seen)", not o or str(o[0][0])!=str(o[0][2])[:10], str(o))
# S5 bytes
reset(); body=feed([("Livelo para Smiles 90% de bônus","https://passageirodeprimeira.com/d1","Mon, 12 Oct 2026 10:00:00 GMT","Livelo para Smiles 90% de bônus de 15/10/2026 a 20/10/2026.")]).encode()
ids=C.collect_rss(engine=eng, source=SRC, url=URL, transport=(lambda u: body), now=T0)
show("S5 feed em bytes (resposta HTTP real) e processado", len(ids)==1, f"raw={len(ids)}")
# S6 sem transport
reset(); ids=C.collect_rss(engine=eng, source=SRC, url=URL, now=T0); show("S6 sem transport faz o fetch HTTP real (producao)", False if ids==[] else True, f"retorno={ids} (fetch_url sem transport devolve None: coletor nao busca nada)")
# S7 robots
reset(); r=C.collect_rss(engine=eng, source=SRC, url=URL, transport=(lambda u: x), robots_txt="User-agent: *\nDisallow: /feed/\n", now=T0)
show("S7 robots bloqueia /feed/ -> 0 itens", r==[], str(r)); print("   S7 source_health:", q("select items_new, alert from source_health"))
show("S7b robots_txt ausente = coleta mesmo assim (spec: reler robots a cada execucao)", False, "sem robots_txt o fetch acontece sem consultar robots; coletor nao baixa robots.txt")
# S8 XML invalido
reset(); r=C.collect_rss(engine=eng, source=SRC, url=URL, transport=(lambda u: "<rss><channel><item><title>x"), now=T0)
print("   S8 xml invalido:", r, "source_health:", q("select items_new, alert, extraction_rate from source_health"), "(erro de parse indistinguivel de 'sem itens')")
# S9 pubDate antigo
reset(); x9=feed([("Livelo para Smiles 90% de bônus","https://passageirodeprimeira.com/e1","Mon, 02 Oct 2023 10:00:00 GMT","Livelo para Smiles 90% de bônus de 05/10/2023 a 10/10/2023.")])
run(x9); o=q("select first_seen_at from offer"); show("S9 item de 2023 no feed: first_seen_at = pubDate (2023)", o and str(o[0][0]).startswith("2023"), str(o))
# S10 sem validacao de negocio
reset(); x10=feed([("a","https://passageirodeprimeira.com/f1","Mon, 12 Oct 2026 10:00:00 GMT","Livelo para Smiles 90% de bônus de 15/10/2026 a 10/10/2026."),
                   ("b","https://passageirodeprimeira.com/f2","Mon, 12 Oct 2026 10:00:00 GMT","Livelo para Smiles 90% de bônus de 01/01/2026 a 30/12/2026.")])
run(x10); o=q("select start_at,end_at,bonus_pct from offer order by id"); print("   S10 offers:", [tuple(map(str,r)) for r in o])
show("S10 fim<inicio e janela>90d nao entram como oferta valida", len(o)==0, f"{len(o)} ofertas gravadas")
# S11 conflito de bonus / segmento
reset(); x11=feed([("Livelo para Smiles","https://passageirodeprimeira.com/g1","Mon, 12 Oct 2026 10:00:00 GMT","Livelo para Smiles 60% de bônus de 15/10/2026 a 20/10/2026. Livelo para Smiles 80% de bônus de 15/10/2026 a 20/10/2026.")])
run(x11); o=q("select segmented, segment_label, bonus_pct from offer"); show("S11 conflito de bonus nao vira segment_label", not o or o[0][1]!="bonus_conflitante", str(o))
# S12 duas fontes: validated
reset(); run(x, source="passageirodeprimeira.com"); run(x, source="www.melhorescartoes.com.br")
o=q("select n_sources, validated, weight from offer order by id"); print("   S12:", [tuple(map(str,r)) for r in o]); show("S12 2 fontes mesma oferta -> n_sources=2 validated", o and o[0][0]==2 and o[0][1], str(o))
# S13 PPV so titulo
reset(); xp=feed([("Livelo e Smiles: 90% de bônus","https://pontospravoar.com/p1","Mon, 12 Oct 2026 10:00:00 GMT","CORPO LONGO DO ARTIGO NAO PODE SER GUARDADO texto texto")])
C.collect_rss(engine=eng, source="pontospravoar.com", url="https://pontospravoar.com/feed/", transport=(lambda u: xp), now=T0)
cont=q("select content from raw_message"); show("S13 PPV guarda so titulo (decisao 002)", cont and "CORPO LONGO" not in cont[0][0], repr(cont[0][0][:60]) if cont else "sem raw")
# S14 backfill
reset(); import preditor.wayback as W
HDR=["urlkey","timestamp","original","mimetype","statuscode","digest","length"]
rows=[HDR,["k","20231005120000","https://passageirodeprimeira.com/promo-a/?utm_source=x","text/html","200","d1","1"],
      ["k","20250705120000","https://passageirodeprimeira.com/promo-a/","text/html","200","d2","1"],
      ["k","20231006120000","https://passageirodeprimeira.com/promo-a/embed/","text/html","200","d3","1"]]
class Stub(W.CDXClient):
    def __init__(self,*a,**k): super().__init__(transport=httpx.MockTransport(lambda r: httpx.Response(200,json=rows)), rate_limit=None, min_interval=0)
C.CDXClient=Stub
pages={}
html=lambda y: f"<html><head><meta property='article:published_time' content='{y}'/></head><body>Livelo para Smiles 90% de bônus de 05/10/2023 a 10/10/2023 {y}</body></html>"
def snap(u):
    pages[u]=1; return html("2023-10-05T10:00:00Z") if "2023" in u else html("2025-07-05")
n=C.backfill(engine=eng, source=SRC, from_="20230101", transport=snap)
c=counts(); print("   S14 backfill:", n, c, "snapshots baixados:", list(pages))
show("S14 backfill: uma URL normalizada -> 1 raw (captura mais antiga)", c["raw_message"]==1, str(c))
o=q("select first_seen_at from offer"); r=q("select collected_at from raw_message")
show("S14b first_seen_at do backfill = data de publicacao/captura antiga, nao now()", o and str(o[0][0]).startswith("2023"), f"first_seen={o[0][0] if o else None} collected_at={r[0][0] if r else None}")
cols=[x[0] for x in q("select column_name from information_schema.columns where table_name='raw_message'")]
show("S14c coluna raw_message.observed_at existe (spec 4.1 item 4)", "observed_at" in cols, str(cols))
# S15 CDX fora do ar no backfill
class Down(W.CDXClient):
    def __init__(self,*a,**k): super().__init__(transport=httpx.MockTransport(lambda r: httpx.Response(503)), rate_limit=None, min_interval=0, max_retries=1)
C.CDXClient=Down; reset(); n=C.backfill(engine=eng, source=SRC, from_="20230101", transport=snap)
print("   S15 CDX 503:", n, q("select items_new, alert from source_health"), "(falha de CDX vira 'backfill de 0 itens' sem erro)")
# S16 XML bomb
bomb='<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;"><!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;"><!ENTITY e "&d;&d;&d;&d;&d;&d;&d;&d;&d;&d;"><!ENTITY f "&e;&e;&e;&e;&e;&e;&e;&e;&e;&e;"><!ENTITY g "&f;&f;&f;&f;&f;&f;&f;&f;&f;&f;"><!ENTITY h "&g;&g;&g;&g;&g;&g;&g;&g;&g;&g;">]><rss><channel><item><title>&h;</title><link>https://x/y</link></item></channel></rss>'
t=time.time(); r=C.parse_feed(bomb); print(f"   S16 XML bomb: {len(r)} itens em {time.time()-t:.2f}s")
big=feed([(f"Livelo para Smiles {i}","https://passageirodeprimeira.com/z%d"%i,"Mon, 12 Oct 2026 10:00:00 GMT","x") for i in range(2000)])
t=time.time(); r=C.parse_feed(big); print(f"   S16b feed 2000 itens: {len(r)} em {time.time()-t:.2f}s")
