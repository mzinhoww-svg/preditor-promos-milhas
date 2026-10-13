import json, sys, time
from harness import *
items=lambda *l: {"updated_at":"2026-10-13","items":list(l)}
def it(i,fase="Setup",peso=1,estado="Feito",**k): return {"id":i,"title":"t "+i,"fase":fase,"peso":peso,"estado":estado,"evidencia":"e","updated_at":"2026-10-13",**k}
P=3350
def run(name, port, **kw):
    d=make(name, **kw); p=start(d, port)
    try:
        raw=get(port); data=json.loads(raw, parse_constant=lambda c: f"<<{c}>>")
        return d,p,raw,data
    finally: p.terminate()
def row(n, **kv): print(f"{n}: "+" ".join(f"{k}={v}" for k,v in kv.items()))
# C1 gh e maestri ausentes (PATH sem eles)
d=make("c1", gh="none", maestri="none", uv="none"); p=start(d,P,keep_path=False)
try:
    data=json.loads(get(P)); row("C1 gh/maestri/uv ausentes", prs=data["prs"], agents={k:data["agents"][k] for k in ("available","error")}, pytest=data["tests"]["pytest"]["available"], overall=round(data["overall_percent"],1), erro=data.get("error"))
finally: p.terminate()
# C2 gh falha com stderr com token
_,_,raw,data=run("c2",P+1,gh="fail"); row("C2 gh 401", prs_error=data["prs"]["error"], vazou_token_fake="ghp_FAKE" in raw)
# C3 gh json invalido / hang
_,_,raw,data=run("c3",P+2,gh="badjson"); row("C3 gh json invalido", prs=data["prs"]["available"], err=data["prs"]["error"])
# C4 maestri falha
_,_,raw,data=run("c4",P+3,maestri="fail"); row("C4 maestri rc!=0", agents=data["agents"])
# C5 checklist vazio / json invalido / ausente
for nm,ck in (("vazio",items()),("lista",[]),("json invalido","{not json"),("so texto","hello")):
    _,_,raw,data=run("c5"+nm.replace(" ",""),P+4,checklist=ck); row(f"C5 checklist {nm}", overall=data["overall_percent"], n_items=data["checklist"]["progress"]["n_items"], erro=data.get("error"), aviso=[k for k in data if "warn" in k or "invalid" in k])
# C6 estados desconhecidos / pesos
_,_,raw,data=run("c6",P+5,checklist=items(it("a",estado="concluida"),it("b",estado="devolvida"),it("c",estado="em_correcao (ciclo 2)"),it("d",estado="Feito"),it("e",estado=None),it("f",estado=7)))
row("C6 estados", overall=round(data["overall_percent"],1), counts=data["checklist"]["progress"]["state_counts"])
for nm,l in (("peso0 todos",[it("a",peso=0),it("b",peso=0,estado="Pendente")]),("100%",[it("a",estado="Feito",peso=3),it("b",estado="Feito",peso=1)]),("0%",[it("a",estado="Pendente"),it("b",estado="Bloqueado")]),("peso negativo",[it("a",peso=-5),it("b",peso=1,estado="Pendente")]),("peso str",[it("a",peso="abc"),it("b",peso="2")]),("peso NaN/inf",[it("a",peso=1e999),it("b",peso=1,estado="Pendente")]),("fase fora",[it("a",fase="Inventada"),it("b",fase="Setup",estado="Pendente")])):
    d=make("c7",checklist=items(*l)); p=start(d,P+6)
    try:
        raw=get(P+6); 
        try: data=json.loads(raw); ok=True
        except Exception as e: ok=False; data=json.loads(raw, parse_constant=lambda c: f"<<{c}>>")
        row(f"C7 {nm}", json_valido=ok, overall=data.get("overall_percent"), phases={k:round(v,1) for k,v in data["phases"].items()} if isinstance(data.get("phases"),dict) else None)
    finally: p.terminate()
# C8 TASKS.md malformado
bad="""# TASKS
| ID | Tarefa
|---|---|
| T1 | so duas colunas |
|||||
| T2 | a | b | c | d | e | f | g |
| <script>alert(1)</script> | x | y | concluida | z |
texto solto
| T3 | tarefa com | pipe \\| escapado | concluida | ok |
"""
_,_,raw,data=run("c8",P+7,tasks=bad); row("C8 TASKS malformado", n_tasks=len(data["tasks"]), tasks=[(t["id"],t["status"]) for t in data["tasks"]])
_,_,raw,data=run("c8b",P+7,tasks="\x00\xff binario"); row("C8b TASKS binario", n=len(data["tasks"]), erro=data.get("error"))
# C9 /data.json segredos
d=make("c9", gh="ok", maestri="ok", uv="secret", status="# STATUS\n## Bloqueios\n- chave OPENROUTER_API_KEY=sk-or-v1-FAKEFAKE\n## Próximos passos\n- x\n")
p=start(d,P+8,extra_env={"DATABASE_URL":"postgresql://u:SUPERSECRETPW@h/db","OPENROUTER_API_KEY":"sk-or-LEAKTEST","GITHUB_TOKEN":"ghp_LEAKTEST"})
try:
    raw=get(P+8); row("C9 vazamento em /data.json", env_DATABASE_URL="SUPERSECRETPW" in raw, env_OPENROUTER="sk-or-LEAKTEST" in raw, env_GH="ghp_LEAKTEST" in raw, status_raw_com_chave="sk-or-v1-FAKEFAKE" in raw, maestri_raw_token="sk-FAKE-SECRET-123" in raw, pytest_tail_senha="S3CRETPW" in raw)
finally: p.terminate()
# C10 testes vermelhos
_,_,raw,data=run("c10",P+9,uv="red"); row("C10 pytest vermelho", pytest=data["tests"]["pytest"])
