import sys, json, time, os, tempfile, random
sys.path.insert(0,"src"); sys.path.insert(0, os.path.dirname(__file__))
from datetime import date, timedelta
from preditor.model import *
from preditor import model as M
exec(open(os.path.join(os.path.dirname(__file__),"probe27.py")).read().split("recs=world()")[0].split("from preditor.model import evaluate_c1_vs_b1")[1])
R={}
recs=world()
def tryit(k,f):
    try: R[k]=f()
    except Exception as e: R[k]=f"EXC {type(e).__name__}: {str(e)[:90]}"
tryit("vazio",lambda: evaluate_c1_vs_b1([],data_source="real"))
tryit("poucos(5)",lambda: evaluate_c1_vs_b1(recs[:5],data_source="real"))
dup=recs+recs
a=evaluate_c1_vs_b1(recs,n_folds=2,n_boot=50,data_source="real")
b=evaluate_c1_vs_b1(dup,n_folds=2,n_boot=50,data_source="real")
R["duplicadas_n_campanhas"]=(sum(a["n_campaigns_by_pair_type"].values()),sum(b["n_campaigns_by_pair_type"].values()))
R["duplicadas_mesmo_p_c1"]=(a["p_c1"]==b["p_c1"] if len(a["p_c1"])==len(b["p_c1"]) else f"len {len(a['p_c1'])} vs {len(b['p_c1'])}")
c=evaluate_c1_vs_b1(recs,n_folds=2,n_boot=50,data_source="real")
R["reexec_deterministico"]=(a["p_c1"]==c["p_c1"] and a["ci_brier"]==c["ci_brier"])
R["n_campanhas_por_par"]={"|".join(k):v for k,v in a["n_campaigns_by_pair_type"].items()}
R["calibrado"]=a["calibrated"]
d=decide_champion(**a["gate_inputs"])
R["decisao_real_n<25?"]=(d["decision"],d["reasons"][:3])
# sinal: C1 pior que B1 (troca) nao pode promover
g=dict(a["gate_inputs"]); g["champion_metrics"],g["challenger_metrics"]=g["challenger_metrics"],g["champion_metrics"]
R["troca_c1_pior_promove?"]=decide_champion(**g)["promoted"]
# ci sign: bootstrap com c1 pior
import random
rnd=random.Random(0); y=[rnd.randint(0,1) for _ in range(300)]
good=[0.8 if v else 0.2 for v in y]; bad=[0.5]*300
bl=[i//7 for i in range(300)]
R["ci_c1_melhor"]=block_bootstrap_ci(y,bad,good,blocks=bl,metric="brier",n_boot=200,seed=1)["ci_low"]>0
R["ci_c1_pior"]=block_bootstrap_ci(y,good,bad,blocks=bl,metric="brier",n_boot=200,seed=1)["ci_low"]<0
# datas conflitantes: first_seen muito depois do start (backfill) / invalido
bad_recs=recs[:]+[mk(date(2024,3,1),"livelo","smiles",fs="não-é-data"), mk(date(2024,3,2),"livelo","smiles",fs=None)]
tryit("datas_invalidas",lambda: len(evaluate_c1_vs_b1(bad_recs,n_folds=2,n_boot=50,data_source="real")["y"]))
# relatorio
tmp=tempfile.mkdtemp(); pth=os.path.join(tmp,"r.md")
record_decision_report(d,path=pth)
R["relatorio_banner"]=("SINTÉTICOS" in open(pth).read())
# tempo predict_proba
t=time.time(); C=M.C1(); 
try:
    p=M.predict_proba(recs,"livelo","smiles","transfer_bonus",as_of=date(2025,5,1),horizon=15,method="c1")
    R["predict_proba_c1"]=(round(p,4),round(time.time()-t,1))
except Exception as e: R["predict_proba_c1"]=f"EXC {type(e).__name__}: {str(e)[:100]}"
print(json.dumps(R,indent=1,default=str))
