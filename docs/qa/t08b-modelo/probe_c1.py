"""Sonda: C1 devolve probabilidades degeneradas? (QA cruzado T08b)"""
import random
from datetime import date, datetime, timedelta, UTC
from preditor.model import C1, predict_proba
from preditor.baseline import predict_proba as bp
rng=random.Random(3)
def mk(o,d,s): return {"origin":o,"destination":d,"event_type":"transfer_bonus","start_at":s,"first_seen_at":datetime.combine(s,datetime.min.time(),UTC)}
H=[]; d=date(2023,1,1)
while d<date(2025,1,1): H.append(mk("livelo","smiles",d)); d+=timedelta(days=rng.randint(10,25))
AS=date(2024,6,1)
for h in (7,15,30):
    print("c1",h,predict_proba(H,"livelo","smiles","transfer_bonus",as_of=AS,horizon=h,method="c1"),
          "b1",h,bp(records=H,origin="livelo",destination="smiles",event_type="transfer_bonus",method="b1",as_of=AS,horizon=h))
m=C1(); m.fit(H,as_of=AS)
print("trained",m.trained,"base_rate",m.base_rate_,"models",{h:type(v).__name__ for h,v in m.models.items()},"cal",{h:(c[0] if c else None) for h,c in m.calibrators.items()})
print("predict()",m.predict("livelo","smiles","transfer_bonus",as_of=AS,horizons=[7,15,30]))
for t in (date(2024,6,1),date(2024,6,20),date(2024,10,1)):
    print("as_of",t,predict_proba(H,"livelo","smiles","transfer_bonus",as_of=t,horizon=15,method="c1"))
