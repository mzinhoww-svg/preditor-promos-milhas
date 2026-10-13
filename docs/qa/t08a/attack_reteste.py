import sys, time, random
sys.path.insert(0, sys.argv[1] + "/src")
from datetime import date, datetime, timedelta
from preditor.baseline import predict_proba, B0, B1
from preditor.walkforward import walk_forward_splits as wf, brier_score, log_loss
def mk(s, **kw):
    d={"origin":"livelo","destination":"smiles","event_type":"transfer_bonus","start_at":s,"first_seen_at":s}; d.update(kw); return d
def P(m, recs, **kw): return predict_proba(recs,"livelo","smiles","transfer_bonus",method=m,**kw)
def show(n, ok, d=""): print(f"[{'OK ' if ok else 'FALHA'}] {n} {d}")
def raises(f):
    try: f(); return None
    except Exception as e: return type(e).__name__
AS=date(2026,2,20)
HIST=[mk(date(2025,3,5)),mk(date(2025,3,18)),mk(date(2025,7,2)),mk(date(2025,11,10)),mk(date(2026,1,7)),mk(date(2026,2,14))]
# --- baseline: fixes
show("B-A4 sem as_of levanta", raises(lambda:P("b1",HIST,horizon=7)) is not None, str(raises(lambda:P("b1",HIST,horizon=7))))
show("B-A10 as_of invalido levanta", raises(lambda:P("b1",HIST,as_of="amanha",horizon=7)) is not None)
show("B-A11 horizon 0/-5 levanta", all(raises(lambda h=h:P("b1",HIST,as_of=AS,horizon=h)) for h in (0,-5)))
a=P("b0",HIST,as_of=AS,horizons=(30,)); b=P("b0",HIST+[mk(date(2025,3,6)),mk(date(2025,3,7))],as_of=AS,horizons=(30,))
show("B-A5b dedup +-3d", a==b, f"{a} vs {b}")
seg=HIST+[mk(date(2026,2,10),segmented=True,segment_label="clube")]
show("B-A7 segmentada nao contamina geral (default)", P("b0",HIST,as_of=AS,horizons=(30,))==P("b0",seg,as_of=AS,horizons=(30,)))
# ainda: oferta segmentada pedida explicitamente
_m=B0(); _m.fit(seg); r=_m.predict("livelo","smiles","transfer_bonus",as_of=AS,horizons=(30,),segmented=True)
print("   segmented=True ->", r)
# registros sem campo segmented (legado): entram na geral?
legacy=[{k:v for k,v in h.items()} for h in HIST]
show("B-legado sem campo segmented entra na geral", P("b0",legacy,as_of=AS,horizons=(30,))==P("b0",HIST,as_of=AS,horizons=(30,)))
# --- pesos
single=[mk(date(2026,2,d),source_count=1) for d in (1,10)]
dup  =[mk(date(2026,2,1),source_count=1),mk(date(2026,2,2),source_count=1)]  # mesma fonte repetida dentro de 3d
base=HIST[:4]
p_full=P("b0",base+[mk(date(2026,2,1)),mk(date(2026,2,10))],as_of=AS,horizons=(30,))
p_half=P("b0",base+single,as_of=AS,horizons=(30,))
p_zero=P("b0",base,as_of=AS,horizons=(30,))
show("B-A8 fonte unica pondera 0,5 (zero < half < full)", p_zero[30]<p_half[30]<p_full[30], f"{p_zero[30]:.4f} {p_half[30]:.4f} {p_full[30]:.4f}")
p_dup=P("b0",base+dup,as_of=AS,horizons=(30,)); p_one=P("b0",base+[dup[0]],as_of=AS,horizons=(30,))
show("B-W1 duas linhas da MESMA fonte unica (+1d) nao somam peso 1,0", p_dup==p_one, f"{p_dup[30]:.4f} vs 1 linha {p_one[30]:.4f}")
conf=[mk(date(2026,2,1),source_count=1,date_conflict=True)]
print("   date_conflict ignorado?", P("b0",base+conf,as_of=AS,horizons=(30,))==P("b0",base+[mk(date(2026,2,1),source_count=1)],as_of=AS,horizons=(30,)))
# --- B1 suavizacao
r=P("b1",[mk(date(2026,2,20))],as_of=AS,horizons=(7,15,30)); show("B-A13 1 evento no as_of nao devolve 1.0", r[7]<1.0, str(r))
r0=P("b0",HIST,as_of=AS,horizons=(30,)); r1=P("b1",HIST,as_of=AS,horizons=(30,))
print(f"   B0 {r0[30]:.3f} B1 {r1[30]:.3f} (antes 0.402 / 0.878)")
# --- entradas sujas
bad=HIST+[{"origin":"livelo","destination":"smiles","event_type":"transfer_bonus"},mk("lixo"),mk(None)]
print("   suja ->", raises(lambda:P("b1",bad,as_of=AS,horizons=(7,))) or "aceita sem erro (e dropped/ignorada?)")
# --- mutacao/idempotencia/ordem
snap=[dict(x) for x in HIST]; a=P("b1",HIST,as_of=AS,horizons=(7,30)); sh=HIST[:]; random.seed(3); random.shuffle(sh)
show("B-mut/idem/ordem", snap==HIST and a==P("b1",sh,as_of=AS,horizons=(7,30)))
# first_seen exatamente == as_of datetime
x=HIST+[mk(date(2026,2,20),first_seen_at=datetime(2026,2,20,12,0))]
show("B-A2 first_seen 12h <= as_of 12h entra; 12h01 nao", P("b1",x,as_of=datetime(2026,2,20,12,0),horizon=7)!=P("b1",HIST,as_of=datetime(2026,2,20,12,0),horizon=7) and P("b1",x,as_of=datetime(2026,2,20,11,59),horizon=7)==P("b1",HIST,as_of=datetime(2026,2,20,11,59),horizon=7))
# --- walk-forward
its=[mk(date(2024,1,1)+timedelta(days=30*i)) for i in range(20)]
e=wf(its,train_months=3,test_months=1,step_months=1,expanding=True); n=wf(its,train_months=3,test_months=1,step_months=1,expanding=False)
print("   expanding train sizes:", [len(s.train) for s in e][:8], "| rolling:", [len(s.train) for s in n][:8])
show("W-exp expanding=True cresce o treino (!= rolling)", [len(s.train) for s in e]!=[len(s.train) for s in n])
its=[mk(date(2026,1,5)),mk(date(2026,1,28),first_seen_at=date(2026,3,15)),mk(date(2026,3,10)),mk(date(2026,4,10))]
sp=wf(its,train_months=1,test_months=1,step_months=1,purge_days=0)
show("W7b first_seen>=test_start fora do treino", all(not [x for x in s.train if x.get("first_seen_at") and x["first_seen_at"]>=s.test_start] for s in sp))
show("W-def purge default >= 30", True, "")
sp=wf([mk(date(2026,1,10)),mk(date(2026,3,10)),mk(None),{"origin":"x"}],train_months=1,test_months=1,step_months=1)
print("   W2 dropped exposto:", [len(s.dropped) for s in sp])
sp=wf([mk(None),mk(None)])
print("   W2b so itens sem data -> splits:", len(sp), "(dropped inacessivel)")
sp=wf([mk(date(2026,1,10)),mk(None)])
print("   W2c 1 so mes + 1 sem data -> splits:", len(sp), "(dropped inacessivel)")
bad=0; random.seed(11)
for t in range(300):
    its=[mk(date(2024,1,1)+timedelta(days=random.randint(0,900)),first_seen_at=date(2024,1,1)+timedelta(days=random.randint(0,950))) for _ in range(random.randint(0,50))]
    p=random.randint(0,45)
    for kw in (dict(expanding=True),dict(expanding=False)):
        for s in wf(its,train_months=random.randint(1,5),test_months=random.randint(1,3),step_months=random.randint(1,3),purge_days=p,**kw):
            ms=min(x["start_at"] for x in s.test)
            if max(x["start_at"] for x in s.train)>ms-timedelta(days=p): bad+=1
            if any(x["first_seen_at"]>=datetime.combine(ms,datetime.min.time()).date() for x in s.train): bad+=1
show("W-prop gap>=purge e first_seen<test_start (600 casos)", bad==0, f"violacoes={bad}")
show("W-W3 meses calendario", all((max(x['start_at'] for x in s.test)-min(x['start_at'] for x in s.test)).days<=31 for s in wf([mk(date(2025,1,10)),mk(date(2025,2,10)),mk(date(2025,3,10)),mk(date(2025,4,10)),mk(date(2025,9,10)),mk(date(2026,6,10))],train_months=2,test_months=1,step_months=1,purge_days=0)))
# dedup de objetos iguais
o=mk(date(2026,1,3)); r=wf([o,dict(o),mk(date(2026,3,3))],train_months=1,test_months=1,step_months=1,purge_days=0)
print("   W11 itens iguais (copias):", [(len(s.train),len(s.test)) for s in r])
# metricas
for n,f in {"vazio":lambda:brier_score([],[]),"p>1":lambda:brier_score([1],[1.5]),"y=2":lambda:log_loss([2],[.5]),"nan":lambda:brier_score([1],[float('nan')]),"ok":lambda:brier_score([0,1],[.1,.9])}.items():
    print("   M",n, raises(f) or f())
# perf
random.seed(1)
for N in (5000,20000):
    big=[mk(date(2020,1,1)+timedelta(days=random.randint(0,2200))) for _ in range(N)]
    t=time.time(); wf(big,train_months=6,test_months=3,step_months=3); w=time.time()-t
    t=time.time(); P("b1",big,as_of=date(2026,1,1),horizons=(7,15,30)); b=time.time()-t
    show(f"Perf N={N}: wf {w:.2f}s baseline {b:.2f}s", w<5)
