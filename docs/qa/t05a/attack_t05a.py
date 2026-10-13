import sys, os, time, threading, json
sys.path.insert(0, sys.argv[1] + "/src")
import httpx
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from preditor import wayback, ingest
from preditor.wayback import CDXClient, list_captures, CDXHTTPError, CDXResponseError
from preditor.ingest import store_raw_message
def show(n, ok, d=""): print(f"[{'OK ' if ok else 'FALHA'}] {n} {d}")
eng = create_engine(os.environ["DATABASE_URL"])
with eng.begin() as c: c.execute(text("TRUNCATE raw_message RESTART IDENTITY CASCADE"))
def rows(): 
    with eng.connect() as c: return c.execute(text("select count(*) from raw_message")).scalar()
def exc(f):
    try: return None, f()
    except Exception as e: return e, None
U="https://www.passageirodeprimeira.com/promo-livelo"
# ---- INGEST
e,r1=exc(lambda: store_raw_message(eng,"pdp",U,"<html>promo 90%</html>","2026-01-02T03:04:05Z"))
e2,r2=exc(lambda: store_raw_message(eng,"pdp",U,"<html>promo 90%</html>","2026-05-05T00:00:00Z"))
show("I1 reingestao idempotente (mesmo id, 1 linha)", r1 and r2 and r1.id==r2.id and rows()==1, f"id {r1 and r1.id}/{r2 and r2.id} linhas={rows()}")
show("I1b reingestao nao altera collected_at original", r2 and r2.collected_at.year==2026 and r2.collected_at.month==1, str(r2 and r2.collected_at))
r3=exc(lambda: store_raw_message(eng,"pdp","https://outra.url/x","<html>promo 90%</html>"))[1]
print("   I1c mesmo conteudo, outra URL, mesma fonte -> id", r3 and r3.id, "url guardada:", r3 and r3.url, "(dedup por (source, hash); URL da 2a captura se perde)")
r4=exc(lambda: store_raw_message(eng,"esfera",U,"<html>promo 90%</html>"))[1]
show("I1d mesma carga em outra fonte cria linha nova", r4 and r4.id!=r1.id)
for name,args in {"vazio":("pdp",U,""),"so espacos":("pdp",U,"  \n\t "),"None":("pdp",U,None),"url vazia":("pdp","","x"),"url sem esquema":("pdp","www.x.com/a","x"),"url javascript":("pdp","javascript:alert(1)","x"),"url file":("pdp","file:///etc/passwd","x"),"url http://":("pdp","http://","x"),"source vazio":("","x://"+U,"x"),"source espacos":("   ",U,"x"),"nul":("pdp",U,"a\x00b"),"collected invalido":("pdp",U,"x","ontem"),"collected int":("pdp",U,"x",12345)}.items():
    e,r=exc(lambda a=args: store_raw_message(eng,*a))
    print(f"   I2 {name}: {'REJEITADO '+type(e).__name__ if e else 'ACEITO id='+str(r.id)}")
n0=rows()
e,r=exc(lambda: store_raw_message(eng,"pdp",U,b"\xff\xfe<html>"))
show("I3 bytes nao-UTF8 rejeitados com erro de dominio", isinstance(e,ingest.IngestError), type(e).__name__ if e else "aceito")
e,r=exc(lambda: store_raw_message(eng,"pdp",U,"abc\ud800def"))
show("I3b surrogate solto em str -> erro de dominio (IngestError)", isinstance(e,ingest.IngestError), type(e).__name__ if e else "aceito")
e,r=exc(lambda: store_raw_message(eng,"pdp",U,"promo ação 90% – até 15/03 \U0001F680"))
show("I3c unicode/emoji ok e round-trip", r and r.content=="promo ação 90% – até 15/03 \U0001F680")
e,r=exc(lambda: store_raw_message(eng,"pdp",U,b"\xef\xbb\xbfbom"))
print("   I3d BOM UTF-8:", repr(r.content) if r else type(e).__name__, "(BOM mantido no conteudo e no hash)")
e,r=exc(lambda: store_raw_message(eng,"pdp","  "+U+"  ","com espacos na url"))
show("I4 URL com espacos nas pontas e normalizada ao guardar", r and r.url==U, repr(r and r.url))
e,r=exc(lambda: store_raw_message(eng,"pdp",U+"\n","url com quebra de linha"))
show("I4b URL com controle/quebra de linha rejeitada", e is not None, repr(r and r.url))
e,r=exc(lambda: store_raw_message(eng,"pdp",U,"futuro","2999-01-01T00:00:00Z"))
show("I5 collected_at no futuro rejeitado", e is not None, str(r and r.collected_at))
e,r=exc(lambda: store_raw_message(eng,"pdp",U,"antigo","1900-01-01"))
print("   I5b collected_at 1900:", "aceito" if r else type(e).__name__)
e,r=exc(lambda: store_raw_message(eng,"pdp",U,["a","b"]))
show("I6 conteudo que nao e str/bytes rejeitado (lista)", e is not None, repr(r and r.content))
# concorrencia
res=[]
def w(): 
    try: res.append(store_raw_message(eng,"pdp",U,"concorrente-unico").id)
    except Exception as ex: res.append(repr(ex))
ts=[threading.Thread(target=w) for _ in range(12)]; [t.start() for t in ts]; [t.join() for t in ts]
show("I7 12 threads mesmo conteudo -> 1 id e 0 erros", len(set(res))==1 and not any(isinstance(x,str) for x in res), str(set(res)))
big="x"*5_000_000; t=time.time(); e,r=exc(lambda: store_raw_message(eng,"pdp",U,big)); print(f"   I8 5 MB: {'ok' if r else type(e).__name__} {time.time()-t:.2f}s")
# ---- CDX
sleeps=[]; wayback.time.sleep=lambda s: sleeps.append(round(s,3))
HDR=["urlkey","timestamp","original","mimetype","statuscode","digest","length"]
def mt(handler): return httpx.MockTransport(handler)
def client(h, **kw): return CDXClient(transport=mt(h), rate_limit=None, min_interval=0, **kw)
def run(h, **kw):
    sleeps.clear(); calls=[]
    def hh(req): calls.append(1); return h(len(calls), req)
    e,r=exc(lambda: client(hh,**kw).list_captures(U)); return e,r,len(calls),list(sleeps)
for name,h in {
  "corpo vazio": lambda n,r: httpx.Response(200, content=b""),
  "[]": lambda n,r: httpx.Response(200, json=[]),
  "so cabecalho": lambda n,r: httpx.Response(200, json=[HDR]),
  "null": lambda n,r: httpx.Response(200, content=b"null"),
  "html no 200": lambda n,r: httpx.Response(200, content=b"<html>Wayback is down</html>"),
  "objeto": lambda n,r: httpx.Response(200, json={"erro":"x"}),
  "linha curta": lambda n,r: httpx.Response(200, json=[HDR,["k","20250101000000"]]),
  "linha nao-lista": lambda n,r: httpx.Response(200, json=[HDR,"lixo",None,123]),
  "sem timestamp": lambda n,r: httpx.Response(200, json=[["urlkey","original"],["k","http://a.com/x"]]),
  "timestamp invalido": lambda n,r: httpx.Response(200, json=[HDR,["k","ontem","http://a.com/x","text/html","200","d","1"]]),
  "bytes nao utf8": lambda n,r: httpx.Response(200, content=b"\xff\xfe[[\"a\"]]"),
}.items():
    e,r,c,s=run(h)
    print(f"   C1 {name}: {('EXC '+type(e).__name__) if e else (str(len(r))+' capturas '+ (json.dumps(dict(r[0]))[:90] if r else ''))}")
for code in (429,500,502,503,504):
    e,r,c,s=run(lambda n,rq,code=code: httpx.Response(code, headers={"Retry-After":"2"}))
    show(f"C2 {code} Retry-After:2 -> {c} tentativas, espera>=2s, erro tipado", c==3 and all(x>=2 for x in s) and e is not None, f"{type(e).__name__} sleeps={s}")
e,r,c,s=run(lambda n,rq: httpx.Response(429, headers={"Retry-After":"2"}))
show("C2b 429 final vira CDXRateLimitError", isinstance(e, wayback.CDXRateLimitError), type(e).__name__)
e,r,c,s=run(lambda n,rq: httpx.Response(503, headers={"Retry-After":"3600"}))
print("   C2c Retry-After 3600:", f"{c} tentativas, esperas {s} (limitado a 60 s; Retry-After do servidor ignorado alem disso)")
e,r,c,s=run(lambda n,rq: httpx.Response(503, headers={"Retry-After":"Wed, 21 Oct 2099 07:28:00 GMT"}))
print("   C2d Retry-After data HTTP:", s)
e,r,c,s=run(lambda n,rq: httpx.Response(503, headers={"Retry-After":"-5"}))
print("   C2e Retry-After negativo:", s)
e,r,c,s=run(lambda n,rq: httpx.Response(503, headers={"Retry-After":"lixo"}))
print("   C2f Retry-After lixo:", c, s)
e,r,c,s=run(lambda n,rq: httpx.Response(503) if n<3 else httpx.Response(200, json=[HDR,["k","20250101000000","http://a.com/x","text/html","200","d","1"]]))
show("C3 503,503,200 -> sucesso", r and len(r)==1 and c==3, f"{e} {c}")
e,r,c,s=run(lambda n,rq: httpx.Response(404))
show("C4 404 nao repete", c==1 and e is not None, f"{c} tentativas")
e,r,c,s=run(lambda n,rq: (_ for _ in ()).throw(httpx.ConnectError("sem rede")))
show("C5 erro de rede -> erro tipado apos retries", isinstance(e, wayback.WaybackError), f"{type(e).__name__} {c} tentativas")
e,r,c,s=run(lambda n,rq: (_ for _ in ()).throw(httpx.ReadTimeout("t")))
show("C5b timeout -> erro tipado", isinstance(e, wayback.WaybackError), f"{type(e).__name__} {c}")
# rate limit funcao de modulo
calls=[]; tcalls=[]
def hm(req): calls.append(time.monotonic()); return httpx.Response(200, json=[HDR])
waits=[]; real_sleep=time.sleep
wayback.time.sleep=lambda s: waits.append(s)
wayback._MODULE_LIMITER=wayback.RateLimiter(rate=1.0); t0=time.monotonic()
for _ in range(4): list_captures(U, transport=mt(hm))
print("   M1 4 chamadas de modulo seguidas (rate 1/s padrao): esperas simuladas =", [round(w,2) for w in waits])
show("M1 limitador de modulo espera entre chamadas", len([w for w in waits if w>0.5])>=3, str([round(w,2) for w in waits]))
waits.clear(); wayback._MODULE_LIMITER=wayback.RateLimiter(rate=1.0)
for _ in range(4): list_captures(U, transport=mt(hm), rate_limit=1.0)
show("M2 passar rate_limit=1.0 por chamada NAO reinicia o limitador (espera entre chamadas)", len([w for w in waits if w>0.5])>=3, str([round(w,2) for w in waits]))
waits.clear()
for _ in range(4): list_captures(U, transport=mt(hm), min_interval=2)
show("M3 min_interval=2 por chamada respeita 2 s entre chamadas", len([w for w in waits if w>1.5])>=3, str([round(w,2) for w in waits]))
