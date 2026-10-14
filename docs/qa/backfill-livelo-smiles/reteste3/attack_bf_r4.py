import json, os, sys, datetime as dt, collections
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor import backfill as B
from preditor.records import load_offer_records
from preditor import model as M
E = create_engine(os.environ["DATABASE_URL"])
P2 = create_engine(os.environ["P2_URL"])
R = {}
def snap(e):
    with e.connect() as c:
        return sorted(tuple(map(str, r)) for r in c.execute(text("SELECT origin,destination,event_type,start_at,end_at,bonus_pct,segmented,segment_label,n_sources,validated FROM offer")))
t0 = B.reprocess(E); s1 = snap(E)
t1 = B.reprocess(E); s2 = snap(E)
R["reprocess_1"] = t0; R["reprocess_2_idempotente"] = (s1 == s2, len(s1), len(s2))
sp2 = snap(P2)
R["mesmo_que_banco_do_autor"] = {"autor": len(sp2), "meu_reprocess": len(s1), "so_no_autor": len(set(sp2) - set(s1)), "so_no_meu": len(set(s1) - set(sp2))}
# gold coverage (livelo->smiles)
camps = [json.loads(l) for l in open("data/gold/campaigns.jsonl")]
offs = [r for r in s1 if r[0] == "livelo" and r[1] == "smiles"]
def d(x): return dt.date.fromisoformat(x)
found = bonus_ok = 0; miss = []
for c in camps:
    if (c["origin"], c["destination"]) != ("livelo", "smiles"): continue
    cand = [o for o in offs if abs((d(o[3]) - d(c["start_at"])).days) <= 3]
    if cand: found += 1
    else: miss.append((c["campaign_id"], c["start_at"], c["split"])); continue
    if any((o[5] != "None" and float(o[5]) == float(c["bonus_pct"])) for o in cand): bonus_ok += 1
by = collections.Counter()
for c in camps:
    if (c["origin"], c["destination"]) != ("livelo", "smiles"): continue
    cand = [o for o in offs if abs((d(o[3]) - d(c["start_at"])).days) <= 3]
    by[(c["split"], "n")] += 1; by[(c["split"], "found")] += bool(cand); by[(c["split"], "bonus")] += any((o[5] != "None" and float(o[5]) == float(c["bonus_pct"])) for o in cand)
R["ouro_cobertura"] = {"campanhas": 49, "encontradas": found, "bonus_correto": bonus_ok, "faltantes": miss, "por_split": {f"{k[0]}:{k[1]}": v for k, v in by.items()}}
# loader gap_only -> evaluate
recs = load_offer_records(E)
R["loader"] = {"n": len(recs), "gap_only": sum(1 for r in recs if r["gap_only"]), "campo_presente": all("gap_only" in r for r in recs)}
kept = M.exclude_gap_only(recs)
R["loader"]["apos_exclude"] = len(kept)
# so-gap realmente fora do evaluate: records so-gap nao podem aparecer em train/test
try:
    ev = M.evaluate_c1_vs_b1(recs, data_source="real", n_boot=20, n_folds=2)
    R["evaluate_com_dados_reais"] = {"linhas": len(ev["y"]), "campanhas_treino": {"|".join(k): v for k, v in ev["n_campaigns_by_pair_type"].items()}, "decisao": M.decide_champion(**ev["gate_inputs"])["decision"]}
except Exception as ex:
    R["evaluate_com_dados_reais"] = f"EXC {type(ex).__name__}: {str(ex)[:150]}"
# controle: recs sem filtro (campo removido) vs com filtro
nog = [{k: v for k, v in r.items() if k != "gap_only"} for r in recs]
try:
    ev2 = M.evaluate_c1_vs_b1(nog, data_source="real", n_boot=20, n_folds=2)
    R["evaluate_sem_filtro_linhas"] = len(ev2["y"])
except Exception as ex:
    R["evaluate_sem_filtro_linhas"] = f"EXC {type(ex).__name__}: {str(ex)[:150]}"
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
