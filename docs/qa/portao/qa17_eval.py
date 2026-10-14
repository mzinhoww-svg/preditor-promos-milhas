import json, os, sys, time
sys.path.insert(0, "src")
from sqlalchemy import create_engine
from preditor.records import load_offer_records
from preditor import model as M
E = create_engine(os.environ["DATABASE_URL"])
recs = load_offer_records(E)
kept = M.exclude_gap_only(recs)
print("registros", len(recs), "apos exclude_gap_only", len(kept), flush=True)
t = time.time()
out = M.run_champion_challenger(kept, data_source="real", n_boot=500)
ev, dec = out["evaluation"], out["decision"]
print("tempo", round(time.time() - t), "s", flush=True)
r = {"dobras": len(ev["folds"]), "cortes": [str(f["cutoff"]) for f in ev["folds"]][:1] + [str(f["cutoff"]) for f in ev["folds"]][-1:], "n_train_por_dobra": [f["n_train"] for f in ev["folds"]],
     "linhas": len(ev["y"]), "positivas": int(sum(ev["y"])), "campanhas_treino": {"|".join(k): v for k, v in ev["n_campaigns_by_pair_type"].items()},
     "brier_b1": ev["metrics"]["b1"]["brier"], "brier_c1": ev["metrics"]["c1"]["brier"], "logloss_b1": ev["metrics"]["b1"]["log_loss"], "logloss_c1": ev["metrics"]["c1"]["log_loss"],
     "ci_brier": [ev["ci_brier"]["ci_low"], ev["ci_brier"]["ci_high"]], "ci_logloss": [ev["ci_logloss"]["ci_low"], ev["ci_logloss"]["ci_high"]], "calibrado": ev["calibrated"],
     "decisao": dec["decision"], "motivos": dec["reasons"]}
print(json.dumps(r, indent=1, default=str, ensure_ascii=False))
