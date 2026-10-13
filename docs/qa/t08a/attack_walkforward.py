import sys, math
sys.path.insert(0, sys.argv[1] + "/src")
from datetime import date, timedelta
from preditor.walkforward import walk_forward_splits as wf, brier_score, log_loss

def mk(d, **kw): return {"origin":"livelo","destination":"smiles","event_type":"transfer_bonus","start_at":d, **kw}
def show(n, ok, d=""): print(f"[{'OK ' if ok else 'FALHA'}] {n} {d}")
def span(items): return min(x["start_at"] for x in items), max(x["start_at"] for x in items)

# W1 purge vs horizonte de rotulo (30d): purge default 15
items=[mk(date(2026,1,d)) for d in (5,20,30)]+[mk(date(2026,2,d)) for d in (2,10)]+[mk(date(2026,3,5))]
sp = wf(items, train_months=1, test_months=1, step_months=1)
for s in sp:
    gap = (s.test_start - s.train_end).days
    print(f"   W1 treino ate {s.train_end} teste de {s.test_start} gap={gap}d  n_train={len(s.train)} n_test={len(s.test)} purged={len(s.purged)}")
show("W1 gap treino->teste >= horizonte maximo (30d) p/ rotulos H=30", all((s.test_start-s.train_end).days>=30 for s in sp), "(default purge_days=15)")

# W2 item sem data descartado em silencio
items2=[mk(date(2026,1,10)), mk(date(2026,3,10)), mk(None), {"origin":"x"}, mk("lixo")]
sp=wf(items2, train_months=1, test_months=1, step_months=1)
tot=sum(len(s.train)+len(s.test)+len(s.purged) for s in sp)
show("W2 itens sem data sao reportados (nao silenciosos)", False, f"3 itens sem data sumiram, sem aviso/contador")

# W3 buracos de meses: 'meses distintos' != meses de calendario
gap=[mk(date(2024,1,15)),mk(date(2024,2,15)),mk(date(2026,1,15)),mk(date(2026,2,15)),mk(date(2026,3,15))]
sp=wf(gap, train_months=2, test_months=1, step_months=1, purge_days=0)
for s in sp: print(f"   W3 treino {span(s.train)} teste {span(s.test)}")
show("W3 janela de treino/teste respeita calendario (sem pular 2 anos)", all((span(s.test)[1]-span(s.test)[0]).days<=31 and (span(s.train)[1]-span(s.train)[0]).days<=62 for s in sp))

# W4 teste de 3 'meses' com buraco
g2=[mk(date(2025,1,10)),mk(date(2025,2,10)),mk(date(2025,3,10)),mk(date(2025,4,10)),mk(date(2025,9,10)),mk(date(2026,6,10))]
sp=wf(g2, train_months=2, test_months=3, step_months=1, purge_days=0)
for s in sp: print(f"   W4 teste {span(s.test)} ({(span(s.test)[1]-span(s.test)[0]).days}d)")

# W5 treino nunca contem item >= test_start, teste nunca antes do treino (varias sementes)
import random
random.seed(7); bad=0
for t in range(200):
    its=[mk(date(2024,1,1)+timedelta(days=random.randint(0,900))) for _ in range(random.randint(0,60))]
    for kw in (dict(expanding=True),dict(expanding=False)):
        for s in wf(its, train_months=random.randint(1,6), test_months=random.randint(1,3), step_months=random.randint(1,4), purge_days=random.randint(0,40), **kw):
            if max(x["start_at"] for x in s.train) >= min(x["start_at"] for x in s.test): bad+=1
show("W5 propriedade: max(train) < min(test) em 400 casos aleatorios", bad==0, f"violacoes={bad}")

# W6 purge em dias respeitado
bad=0
for t in range(200):
    p=random.randint(0,40)
    its=[mk(date(2024,1,1)+timedelta(days=random.randint(0,900))) for _ in range(60)]
    for s in wf(its, train_months=3, test_months=1, step_months=1, purge_days=p):
        if (min(x["start_at"] for x in s.test)-max(x["start_at"] for x in s.train)).days < p: bad+=1
show("W6 propriedade: gap >= purge_days", bad==0, f"violacoes={bad}")

# W7 first_seen_at: treino com item cujo first_seen cai no periodo de teste
its=[mk(date(2026,1,5)), mk(date(2026,1,28), first_seen_at=date(2026,3,2)), mk(date(2026,3,10)), mk(date(2026,4,10))]
sp=wf(its, train_months=1, test_months=1, step_months=1, purge_days=0)
for s in sp:
    leak=[x for x in s.train if x.get("first_seen_at") and x["first_seen_at"]>=s.test_start]
    print(f"   W7 split teste {s.test_start}: itens de treino com first_seen>=test_start: {len(leak)}")
show("W7 treino so contem itens cujo first_seen_at < test_start", all(not [x for x in s.train if x.get('first_seen_at') and x['first_seen_at']>=s.test_start] for s in sp))

# W8 date_field alternativo 'first_seen_at' com fallback silencioso a start_at
its=[{"start_at":date(2026,1,5)},{"start_at":date(2026,3,5),"first_seen_at":date(2026,1,6)},{"start_at":date(2026,3,9)}]
sp=wf(its, date_field="first_seen_at", train_months=1, test_months=1, step_months=1, purge_days=0)
print("   W8", [(s.train_end,s.test_start,len(s.test)) for s in sp])

# W9 entrada vazia / um unico mes / gerador / None
for n,v in (("vazio",[]),("None",None),("1 mes",[mk(date(2026,1,3))]),("gerador",(mk(date(2026,m,3)) for m in range(1,6)))):
    try: print(f"   W9 {n}: {len(wf(v))} splits")
    except Exception as e: print(f"   W9 {n}: EXC {e!r}")
# W10 parametros invalidos
for kw in (dict(train_months=0),dict(test_months=-1),dict(step_months=0),dict(purge_days=-5)):
    try: print("   W10",kw,len(wf([mk(date(2026,m,3)) for m in range(1,9)],**kw)),"splits (sem erro; clamp silencioso)")
    except Exception as e: print("   W10",kw,"EXC",repr(e))
# W11 duplicatas na entrada (mesmo objeto 2x) e ids
o=mk(date(2026,1,3)); its=[o,o,mk(date(2026,3,3))]
s=wf(its, train_months=1,test_months=1,step_months=1,purge_days=0)
print("   W11 objeto duplicado ->", [(len(x.train),len(x.test)) for x in s])
# W12 reexecucao
a=[(s.train_end,s.test_start,len(s.train),len(s.test)) for s in wf(g2,train_months=2,test_months=1,step_months=1)]
b=[(s.train_end,s.test_start,len(s.train),len(s.test)) for s in wf(list(reversed(g2)),train_months=2,test_months=1,step_months=1)]
show("W12 idempotente e independe da ordem", a==b)
# W13 particao: todo item datado aparece em exatamente um lugar por split (train/test/purged/ fora)?
its=[mk(date(2026,m,d)) for m in range(1,9) for d in (3,17)]
s=wf(its, train_months=3,test_months=1,step_months=1,purge_days=15)[0]
ids=[id(x) for x in s.train]+[id(x) for x in s.test]+[id(x) for x in s.purged]
show("W13 sem item em dois conjuntos", len(ids)==len(set(ids)))
# W14 purged inclui itens do mes de treino apos cutoff; e itens entre cutoff e test_min de meses nao treino?
print("   W14 purged:", sorted(x["start_at"].isoformat() for x in s.purged), "train_end", s.train_end, "test_start", s.test_start)
# W15 metricas
print("   M1 vazio brier/logloss:", brier_score([],[]), log_loss([],[]), "(0.0 = 'perfeito' p/ vazio)")
for n,y,p in (("p>1",[1],[1.5]),("p<0",[0],[-0.2]),("y=2",[2],[0.5]),("nan",[1],[float('nan')]),("len",[1,0],[0.5])):
    try: print(f"   M2 {n}: brier={brier_score(y,p)} logloss={log_loss(y,p)}")
    except Exception as e: print(f"   M2 {n}: EXC {e!r}")
