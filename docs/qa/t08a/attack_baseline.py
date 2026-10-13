import sys, time, math, random
sys.path.insert(0, sys.argv[1] + "/src")
from datetime import date, datetime, timedelta
from preditor.baseline import B0, B1, predict_proba
from preditor.walkforward import walk_forward_splits, brier_score, log_loss

def mk(start, fs=None, **kw):
    d = {"origin":"livelo","destination":"smiles","event_type":"transfer_bonus","start_at":start,"first_seen_at":fs if fs is not None else start}
    d.update(kw); return d

def P(model, recs, **kw):
    return predict_proba(recs, "livelo","smiles","transfer_bonus", method=model, **kw)

def show(name, ok, detail=""):
    print(f"[{'OK ' if ok else 'FALHA'}] {name} {detail}")

HIST = [mk(date(2025,3,5)), mk(date(2025,3,18)), mk(date(2025,7,2)), mk(date(2025,11,10)), mk(date(2026,1,7)), mk(date(2026,2,14))]
AS = date(2026,2,20)

# A1 vazamento: evento com start<=as_of mas first_seen > as_of
leak = HIST + [mk(date(2026,2,18), fs=date(2026,3,5))]
for m in ("b0","b1"):
    a = P(m, HIST, as_of=AS, horizons=(7,15,30)); b = P(m, leak, as_of=AS, horizons=(7,15,30))
    show(f"A1 {m} first_seen>as_of ignorado", a==b, f"{a} vs {b}")

# A2 vazamento: first_seen no mesmo dia as_of mas datetime posterior (hora)
fs_late = datetime(2026,2,20,23,0)
x = HIST + [mk(date(2026,2,20), fs=fs_late)]
a = P("b1", HIST, as_of=datetime(2026,2,20,8,0), horizon=7); b = P("b1", x, as_of=datetime(2026,2,20,8,0), horizon=7)
show("A2 first_seen 23h > as_of 08h (mesmo dia) ignorado", a==b, f"{a} vs {b}")

# A3 evento futuro (start>as_of) altera?
fut = HIST + [mk(date(2026,2,25)), mk(date(2026,3,3))]
for m in ("b0","b1"):
    show(f"A3 {m} start futuro ignorado", P(m,HIST,as_of=AS,horizons=(7,15,30))==P(m,fut,as_of=AS,horizons=(7,15,30)))

# A4 as_of ausente => usa max(start) (inclui tudo)
a = P("b1", HIST, horizon=7)
show("A4 sem as_of nao levanta erro e vira 'ultimo start' (silencioso)", True, f"p={a}")
# A4b sem as_of, com historico vazio -> date.today()
print("   A4b vazio sem as_of:", P("b1", [], horizon=7))

# A5 B0 outras entradas: duplicatas (mesma campanha repetida 3x) alteram a taxa?
dup = HIST + HIST
show("A5 duplicatas exatas nao mudam B0", P("b0",HIST,as_of=AS,horizons=(7,30))==P("b0",dup,as_of=AS,horizons=(7,30)))
# A5b duplicatas dentro de +-3 dias (glossario: mesma campanha)
near = HIST + [mk(date(2025,3,6)), mk(date(2025,3,7))]
a=P("b0",HIST,as_of=AS,horizons=(30,)); b=P("b0",near,as_of=AS,horizons=(30,))
show("A5b +-3d mesma campanha dedup (glossario)", a==b, f"{a} vs {b}")

# A6 par/tipo errado nao contamina
other = HIST + [mk(date(2026,2,10), origin="esfera")] + [mk(date(2026,2,11), event_type="purchase_discount")]
show("A6 outro par/tipo nao contamina", P("b0",HIST,as_of=AS,horizons=(30,))==P("b0",other,as_of=AS,horizons=(30,)))

# A7 segmentada: oferta segmentada contamina oferta geral?
seg = HIST + [mk(date(2026,2,10), segmented=True, segment_label="clube")]
m = B0(); m.fit(seg)
a = m.predict("livelo","smiles","transfer_bonus", as_of=AS, horizons=(30,))
m2 = B0(); m2.fit(HIST)
b = m2.predict("livelo","smiles","transfer_bonus", as_of=AS, horizons=(30,))
show("A7 segmentada nao entra em oferta geral (segmented=False)", a==b, f"{a} vs {b}")
m3=B0(); m3.fit(seg)
c = m3.predict("livelo","smiles","transfer_bonus", as_of=AS, horizons=(30,), segmented=False)
show("A7b segmented=False exclui segmentada", c==b, f"{c} vs {b}")

# A8 fonte unica peso 0,5 / date_conflict : campos ignorados?
w = HIST + [mk(date(2026,2,10), source_count=1, validated=False, date_conflict=True)]
show("A8 peso 0,5 fonte unica refletido", P("b0",HIST,as_of=AS,horizons=(30,))!=P("b0",w,as_of=AS,horizons=(30,)) , "(esperado: mudar, mas com peso 0,5)")

# A9 entradas sujas
bad = HIST + [{"origin":"livelo","destination":"smiles","event_type":"transfer_bonus"}, mk("lixo"), mk(None), mk("2026-13-45")]
try:
    r = P("b1", bad, as_of=AS, horizons=(7,30)); show("A9 registros sem data/data invalida nao quebram", True, str(r))
except Exception as e: show("A9", False, repr(e))
# A10 as_of invalido
try:
    r = P("b1", HIST, as_of="amanha", horizon=7); show("A10 as_of invalido", False, f"aceitou silenciosamente: {r}")
except Exception as e: show("A10 as_of invalido levanta", True, repr(e))
# A11 horizonte 0 / negativo / gigante
for h in (0,-5,3650):
    try: print("   A11 horizon", h, P("b1",HIST,as_of=AS,horizon=h))
    except Exception as e: print("   A11 horizon",h,"EXC",repr(e))
# A12 monotonia B1 em horizontes, e [0,1]
r = P("b1",HIST,as_of=AS,horizons=(1,7,15,30,60,90,365))
show("A12 B1 monotono", all(r[a]<=r[b] for a,b in zip(sorted(r),sorted(r)[1:])), str(r))
# A13 taxa degenerada: um unico evento
r = P("b0",[mk(date(2026,2,14))],as_of=AS,horizons=(7,15,30)); print("   A13 1 evento B0:", r)
r = P("b0",[mk(date(2026,2,20))],as_of=AS,horizons=(7,15,30)); print("   A13b 1 evento no as_of B0:", r)
r = P("b1",[mk(date(2026,2,20))],as_of=AS,horizons=(7,15,30)); print("   A13c 1 evento no as_of B1:", r)
# A14 todos eventos em dias consecutivos => rate 1.0
r = P("b0",[mk(date(2026,2,d)) for d in range(1,21)],as_of=AS,horizons=(7,)); print("   A14 rate=1:", r)
# A15 B1 reajuste sazonal: mes futuro sem obs => fallback global; mes sem eventos mas observado => 0 hazard
h = [mk(date(2025,3,5)), mk(date(2025,3,18)), mk(date(2026,2,14))]
r = P("b1",h,as_of=date(2026,2,20),horizons=(30,)); print("   A15 B1 maio zerado?", r)
# A16 Performance
random.seed(1)
big=[mk(date(2020,1,1)+timedelta(days=random.randint(0,2200))) for _ in range(5000)]
t=time.time(); P("b1",big,as_of=date(2026,1,1),horizons=(7,15,30)); print(f"   A16 B1 5000 recs: {time.time()-t:.2f}s")
t=time.time(); walk_forward_splits(big, train_months=6,test_months=3,step_months=3); print(f"   A16 walkforward 5000 recs: {time.time()-t:.2f}s")
# A17 mutacao de entrada
snap=[dict(x) for x in HIST]; P("b1",HIST,as_of=AS,horizons=(7,)); show("A17 nao muta entrada", snap==HIST)
# A18 reexecucao idempotente
show("A18 idempotente", P("b1",HIST,as_of=AS,horizons=(7,15,30))==P("b1",HIST,as_of=AS,horizons=(7,15,30)))
# A19 B1 usa as_of como fim da janela; prever em t com dado ate t NAO deve depender de dados > t com start<=t? (coberto A1)
# A20 ordem de entrada
sh=HIST[:]; random.shuffle(sh)
show("A20 independe da ordem", P("b1",HIST,as_of=AS,horizons=(7,30))==P("b1",sh,as_of=AS,horizons=(7,30)))
