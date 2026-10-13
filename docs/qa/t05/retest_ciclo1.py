import sys, os; sys.path.insert(0,sys.argv[1]+"/src")
import httpx
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from preditor import collector as C
import preditor.wayback as W
eng=create_engine(os.environ["DATABASE_URL"])
def reset():
    with eng.begin() as c: c.execute(text("TRUNCATE offer_evidence, offer, raw_message, source_health RESTART IDENTITY CASCADE"))
def q(s):
    with eng.connect() as c: return c.execute(text(s)).fetchall()
T0=datetime(2026,10,13,12,0,tzinfo=timezone.utc); SRC="passageirodeprimeira.com"; FU="https://passageirodeprimeira.com/feed/"
feed='<?xml version="1.0"?><rss><channel><item><title>Livelo para Smiles: 90% de bônus</title><link>https://passageirodeprimeira.com/a1</link><pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate><description>Livelo para Smiles com 90% de bônus de 15/10/2026 a 20/10/2026.</description></item></channel></rss>'
calls=[]
class R:
    def __init__(s,t): s.text=t; s.content=t.encode()
def fake_real(url, headers=None):
    calls.append(url); return R(feed if "feed" in url else "User-agent: *\nAllow: /\n")
C._fetch_url_real=fake_real; reset()
try: ids=C.collect_rss(engine=eng, source=SRC, url=FU, now=T0); print("S6 sem transport ->", ids, "chamadas HTTP:", calls)
except Exception as e: print("S6 EXC", type(e).__name__, e)
calls.clear()
def fake_block(url, headers=None):
    calls.append(url); return R("User-agent: *\nDisallow: /feed/\n" if "robots" in url else feed)
C._fetch_url_real=fake_block; reset()
ids=C.collect_rss(engine=eng, source=SRC, url=FU, now=T0); print("S7 robots.txt baixado e respeitado ->", ids, "chamadas:", calls)
reset()
try: ids=C.collect_rss(engine=eng, source=SRC, url=FU, transport=(lambda u: feed.encode() if "feed" in u else b"User-agent: *\nAllow: /\n"), now=T0); print("S5 bytes ->", ids)
except Exception as e: print("S5 EXC", type(e).__name__, str(e)[:100])
reset(); tr=(lambda u: feed if "feed" in u else "User-agent: *\nAllow: /\n")
C.collect_rss(engine=eng, source=SRC, url=FU, transport=tr, now=T0)
try: C.collect_rss(engine=eng, source=SRC, url=FU, transport=tr, now=T0); print("S2 2a execucao mesmo now: ok")
except Exception as e: print("S2 2a execucao com mesmo now ->", type(e).__name__)
reset(); r=C.collect_rss(engine=eng, source=SRC, url=FU, transport=(lambda u: "<rss><item>" if "feed" in u else ""), now=T0)
print("S8 xml invalido ->", r, q("select items_new, alert, extraction_rate, left(robots_hash,6) from source_health"))
HDR=["urlkey","timestamp","original","mimetype","statuscode","digest","length"]
rows=[HDR,["k","20231005120000","https://passageirodeprimeira.com/promo-a/?utm_source=x","text/html","200","d1","1"],["k","20250705120000","https://passageirodeprimeira.com/promo-a/","text/html","200","d2","1"]]
class Stub(W.CDXClient):
    def __init__(self,*a,**k): super().__init__(transport=httpx.MockTransport(lambda r: httpx.Response(200,json=rows)), rate_limit=None, min_interval=0)
C.CDXClient=Stub
html="<html><head><meta property='article:published_time' content='2023-10-04T10:00:00Z'/></head><body>Livelo para Smiles 90% de bônus de 05/10/2023 a 10/10/2023</body></html>"
for fr in (None, "202301", "20230101"):
    reset()
    try:
        n=C.backfill(engine=eng, source=SRC, from_=fr, transport=(lambda u: html)) if fr else C.backfill(engine=eng, source=SRC, transport=(lambda u: html))
        print(f"B1 backfill from_={fr!r} ->", n, q("select count(*) from raw_message")[0][0], "raw")
    except Exception as e: print(f"B1 from_={fr!r} EXC", type(e).__name__, str(e)[:80])
reset(); C.backfill(engine=eng, source=SRC, from_="20230101", transport=(lambda u: html))
print("observed_at backfill:", q("select observed_at, collected_at from raw_message"), "first_seen:", q("select first_seen_at from offer"))
class Bad:
    def begin(s): raise RuntimeError("db down")
    def connect(s): raise RuntimeError("db down")
try: C.collect_rss(engine=Bad(), source=SRC, url=FU, transport=tr, now=T0); print("B4 DB fora do ar: silencioso")
except Exception as e: print("B4 DB fora do ar ->", type(e).__name__, e)
