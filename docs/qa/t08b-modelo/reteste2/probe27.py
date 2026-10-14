import sys, json, hashlib, random
from datetime import date, timedelta
sys.path.insert(0, "src")
from preditor.model import evaluate_c1_vs_b1
def mk(start, o, d, fs=None, tp="transfer_bonus", bonus=80):
    return {"origin":o,"destination":d,"event_type":tp,"start_at":start,"first_seen_at":fs if fs is not None else start,"bonus_pct":bonus}
def world(seed=7):
    rnd=random.Random(seed); recs=[]
    for (o,d,step) in (("livelo","smiles",14),("esfera","latam",21),("itau","azul",17)):
        t=date(2023,1,1)
        while t<date(2025,6,1):
            recs.append(mk(t,o,d,fs=t-timedelta(days=rnd.randint(0,3)),bonus=rnd.choice([60,80,100,120])))
            t+=timedelta(days=step+rnd.randint(-3,3))
    return recs
recs=world()
ev=evaluate_c1_vs_b1(recs,n_folds=2,n_boot=50,data_source="real",train_months=6)
h=hashlib.sha1(json.dumps([round(x,9) for x in ev["p_c1"]]).encode()).hexdigest()[:12]
hb=hashlib.sha1(json.dumps([round(x,9) for x in ev["p_b1"]]).encode()).hexdigest()[:12]
# invariancia: injeta ofertas "tardias" (fs apos o fim do teste) com start dentro da janela de teste -> p_c1/p_b1 das linhas comuns nao pode mudar
rnd=random.Random(1)
late=[mk(r["start_at"]+timedelta(days=2),r["origin"],r["destination"],fs=date(2026,6,1)+timedelta(days=i),bonus=300)
      for i,r in enumerate(rnd.sample(recs,40))]
ev2=evaluate_c1_vs_b1(recs+late,n_folds=2,n_boot=50,data_source="real",train_months=6)
def idx(e): return {k:(b,c) for k,b,c in zip(zip(e["origin"],e["destination"],e["event_type"],e["t"],e["h"]),e["p_b1"],e["p_c1"])}
a,b=idx(ev),idx(ev2); common=set(a)&set(b)
diff=[k for k in common if a[k]!=b[k]]
print(json.dumps({"n":len(ev["y"]),"p_c1_hash":h,"p_b1_hash":hb,"common":len(common),"changed_by_late_records":len(diff),
                  "brier_b1":round(ev["metrics"]["b1"]["brier"],5),"brier_c1":round(ev["metrics"]["c1"]["brier"],5)}))
