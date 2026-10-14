"""QA cruzado T08b: vazamento temporal, determinismo, bordas, portao de decisao. Sem banco."""
import time, random, tempfile, os
from datetime import date, datetime, timedelta, UTC
import numpy as np
from preditor import model as M
if os.getenv("QA_SHIM"):  # contorna o bug do autor SOMENTE para explorar o resto (nao altera o codigo do autor)
    _o = M._first_seen_dt
    M._first_seen_dt = lambda v: _o(v.get("first_seen_at") if isinstance(v, dict) else v)
from preditor.model import C1, build_daily_grade, predict_proba, block_bootstrap_ci, decide_champion, record_decision_report
def show(t, v): print(f"[{t}] {v}", flush=True)
def mk(o,d,start,fs=None,et="transfer_bonus"):
    return {"origin":o,"destination":d,"event_type":et,"start_at":start,"first_seen_at":fs or datetime.combine(start,datetime.min.time(),UTC)}
rng=random.Random(7)
def synth(n_pairs=3, years=2, step=(10,25)):
    out=[]; 
    for i in range(n_pairs):
        d=date(2023,1,1)+timedelta(days=rng.randint(0,10))
        while d<date(2023,1,1)+timedelta(days=365*years):
            out.append(mk(f"P{i}","Smiles",d)); d+=timedelta(days=rng.randint(*step))
    return out
H=synth()
# L1 invariancia a oferta futura (first_seen > as_of)
AS=date(2024,6,1)
fut=[mk("P0","Smiles",date(2024,6,10)),mk("P0","Smiles",date(2024,7,1))]
a=predict_proba(H,"P0","Smiles","transfer_bonus",as_of=AS,horizon=15,method="c1")
b=predict_proba(H+fut,"P0","Smiles","transfer_bonus",as_of=AS,horizon=15,method="c1")
show("L1 first_seen futuro nao altera prob", (a==b,a,b))
# L2 oferta com start<=as_of mas first_seen>as_of (descoberta tardia/backfill)
late=[mk("P0","Smiles",date(2024,5,25),fs=datetime(2024,8,1,tzinfo=UTC))]
c=predict_proba(H+late,"P0","Smiles","transfer_bonus",as_of=AS,horizon=15,method="c1")
show("L2 backfill (first_seen>as_of) nao altera prob", (c==a,c))
# L3 first_seen ausente
nofs=[{"origin":"P0","destination":"Smiles","event_type":"transfer_bonus","start_at":date(2024,5,30)}]
try:
    d_=predict_proba(H+nofs,"P0","Smiles","transfer_bonus",as_of=AS,horizon=15,method="c1"); show("L3 sem first_seen_at", (d_==a, d_))
except Exception as e: show("L3 sem first_seen_at", f"EXCECAO {type(e).__name__}: {e}")
# L4 first_seen naive/string
try:
    s=[mk("P0","Smiles",date(2024,5,30),fs="2024-05-30T00:00:00")]
    show("L4 first_seen string/naive", predict_proba(H+s,"P0","Smiles","transfer_bonus",as_of=AS,horizon=15,method="c1"))
except Exception as e: show("L4 first_seen string", f"EXCECAO {type(e).__name__}: {e}")
# D determinismo
r=[predict_proba(H,"P0","Smiles","transfer_bonus",as_of=AS,horizon=15,method="c1") for _ in range(3)]
show("D determinismo 3 execucoes", r)
# G grade: rotulos com censura a direita / embargo
g=build_daily_grade([r_ for r_ in H if r_["origin"]=="P0"],horizons=[30])
last=max(x["start_at"] for x in H if x["origin"]=="P0")
tail=[x for x in g if x["t"]>last-timedelta(days=30)]
show("G1 grade: t no fim do historico (janela > dados) rotulado", {"n":len(tail),"y1":sum(x["y"] for x in tail),"maxT":str(max(x["t"] for x in g)),"last_offer":str(last)})
# G2 embargo no treino do C1.fit: linhas cujo rotulo cruza as_of
rows=build_daily_grade([x for x in H if x["first_seen_at"].date()<=AS],horizons=[30])
show("G2 C1.fit usa grade sem embargo_cutoff: linhas com t+h>as_of", sum(1 for x in rows if x["t"]+timedelta(days=x["h"])>AS))
# T tempo
big=synth(n_pairs=4, years=2)
t0=time.time(); gg=build_daily_grade(big,horizons=[7,15,30]); t1=time.time()
show("T grade 4 pares x 2 anos x 3 horizontes", {"n_offers":len(big),"rows":len(gg),"seg":round(t1-t0,1)})
t0=time.time(); predict_proba(big,"P0","Smiles","transfer_bonus",as_of=date(2025,12,31),horizon=15,method="c1"); show("T predict_proba(c1) 1 par", round(time.time()-t0,1))
# E bordas
for name,rec in [("vazio",[]),("1 oferta",[mk("P0","Smiles",date(2024,1,1))]),("duplicadas",[mk("P0","Smiles",date(2024,1,1))]*50)]:
    try: show(f"E {name}", predict_proba(rec,"P0","Smiles","transfer_bonus",as_of=AS,horizon=15,method="c1"))
    except Exception as e: show(f"E {name}", f"EXCECAO {type(e).__name__}: {e}")
try: show("E par desconhecido", predict_proba(H,"X","Y","transfer_bonus",as_of=AS,horizon=15,method="c1"))
except Exception as e: show("E par desconhecido", f"EXCECAO {type(e).__name__}: {e}")
try: show("E sem as_of", predict_proba(H,"P0","Smiles","transfer_bonus",horizon=15,method="c1"))
except Exception as e: show("E sem as_of", f"EXCECAO {type(e).__name__}: {e}")
p=predict_proba(H,"P0","Smiles","transfer_bonus",as_of=AS,horizons=[7,15,30],method="c1"); show("E monotonia p7<=p15<=p30", p)
# B bootstrap / decisao: convencao de sinal
y=[0,0,1,1]*30; pb=[0.5]*len(y); pc=[0.9 if v else 0.1 for v in y]
bl=[i//5 for i in range(len(y))]
ci=block_bootstrap_ci(y,pb,pc,blocks=bl,metric="brier",n_boot=300,seed=1)
show("B1 ci C1 melhor que B1 (brier)", ci)
brier=lambda p:float(np.mean((np.array(p)-np.array(y))**2))
dec=decide_champion(champion_metrics={"brier":brier(pb),"log_loss":0.69},challenger_metrics={"brier":brier(pc),"log_loss":0.1},
   bootstrap_ci_brier=ci, bootstrap_ci_logloss=block_bootstrap_ci(y,pb,pc,blocks=bl,metric="log_loss",n_boot=300,seed=1), challenger_calibrated=True)
show("B2 decide_champion com saida direta do bootstrap (C1 claramente melhor)", {k:dec[k] for k in ("decision","promoted","note")})
# B3 so uma metrica / sem ic
show("B3 sem IC", decide_champion(champion_metrics={"brier":.2,"log_loss":.6},challenger_metrics={"brier":.1,"log_loss":.3},challenger_calibrated=True)["decision"])
# R relatorio
tmp=os.path.join(tempfile.mkdtemp(),"r.md"); record_decision_report({"decision":"promote_challenger","note":"C1 vence"},path=tmp)
txt=open(tmp).read()
show("R1 relatorio de decisao PROMOVER continua rotulado sintetico/B1 permanece", ("SINT" in txt, "permanece em produ" in txt))
