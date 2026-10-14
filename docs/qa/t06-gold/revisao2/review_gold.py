import json, re, sys, collections, random, os
from pathlib import Path
G = Path(sys.argv[1])
camps = [json.loads(l) for l in (G/"campaigns.jsonl").read_text().splitlines() if l.strip()]
msgs = [json.loads(l) for l in (G/"messages.jsonl").read_text().splitlines() if l.strip()]
R = {}
R["n_campanhas"] = len(camps); R["n_mensagens"] = len(msgs)
R["status_campanhas"] = dict(collections.Counter(c["status"] for c in camps))
R["status_mensagens"] = dict(collections.Counter(m["status"] for m in msgs))
R["split_campanhas"] = dict(collections.Counter(c["split"] for c in camps))
R["split_distratores"] = dict(collections.Counter(m["split"] for m in msgs if m["kind"] != "positive"))
R["kinds"] = dict(collections.Counter(m["kind"] for m in msgs))
R["blocos"] = dict(collections.Counter(c.get("block") for c in camps))
R["pares"] = dict(collections.Counter(f'{c["origin"]}->{c["destination"]}:{c["event_type"]}' for c in camps))
R["anos_inicio"] = dict(sorted(collections.Counter(c["start_at"][:4] for c in camps).items()))
R["validadas"] = sum(1 for c in camps if c["validated"]); R["fonte_unica"] = sum(1 for c in camps if not c["validated"])
tl = [len(m["text"]) for m in msgs]
R["texto_max_chars"] = max(tl); R["texto_total_chars"] = sum(tl); R["texto_>600"] = sum(1 for x in tl if x > 600)
R["texto_com_html"] = sum(1 for m in msgs if re.search(r"<[a-zA-Z/][^>]*>", m["text"]))
R["campos_proibidos"] = sorted({k for m in msgs for k in m if k in ("content", "html", "body", "raw", "article")})
R["url_em_todos"] = all(m.get("url", "").startswith("http") for m in msgs)
ids = {m["gold_id"] for m in msgs}
R["evidence_ids_orfaos"] = [e for c in camps for e in c["evidence_ids"] if e not in ids]
R["msgs_sem_campanha(positivas)"] = [m["gold_id"] for m in msgs if m["kind"] == "positive" and not m["campaign_ids"]]
cid = {c["campaign_id"]: c for c in camps}
inc = []
for m in msgs:
    for c in m["campaign_ids"]:
        if c not in cid: inc.append((m["gold_id"], c))
        elif cid[c]["split"] != m["split"]: inc.append((m["gold_id"], c, "split"))
R["inconsistencias_campanha_msg"] = inc
# first_seen = min observed_at das evidencias
bad = []
mm = {m["gold_id"]: m for m in msgs}
for c in camps:
    obs = sorted(mm[e]["observed_at"] for e in c["evidence_ids"] if e in mm)
    if obs and c["first_seen_at"] != obs[0]: bad.append((c["campaign_id"], c["first_seen_at"], obs[0]))
R["first_seen_nao_minimo"] = bad
gapbad = [c["campaign_id"] for c in camps if c["all_evidence_gap"] != all(mm[e]["published_vs_capture_gap"] for e in c["evidence_ids"])]
R["all_evidence_gap_inconsistente"] = gapbad; R["all_evidence_gap_n"] = sum(c["all_evidence_gap"] for c in camps)
tags = collections.Counter(t for m in msgs for t in m["tags"]); R["tags"] = dict(tags)
# schema
try:
    import jsonschema
    from referencing import Registry, Resource
    of = json.loads(Path(os.environ["OFERTA_SCHEMA"]).read_text()) if os.environ.get("OFERTA_SCHEMA") else {}
    reg = Registry().with_resource(of.get("$id","x"), Resource.from_contents(of, default_specification=__import__("referencing.jsonschema",fromlist=["x"]).DRAFT202012)) if of else Registry()
    sc = json.loads((G/"schema/campaign.schema.json").read_text()); sm = json.loads((G/"schema/message.schema.json").read_text())
    ec = [str(e.message)[:80] for c in camps for e in jsonschema.Draft202012Validator(sc, registry=reg).iter_errors(c)]
    em = [str(e.message)[:80] for m in msgs for e in jsonschema.Draft202012Validator(sm, registry=reg).iter_errors(m)]
    R["schema_erros"] = {"campanhas": ec[:5], "mensagens": em[:5], "n": len(ec)+len(em)}
except ImportError: R["schema_erros"] = "jsonschema ausente"
# prazos: inicio/fim ano
R["datas_<2023"] = sum(1 for c in camps if c["start_at"] < "2023-01-01")
print(json.dumps(R, indent=1, ensure_ascii=False))
