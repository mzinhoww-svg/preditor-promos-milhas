import json, os
from harness2 import *
it=lambda i,**k: {"id":i,"title":"t "+i,"fase":"Setup","peso":1,"estado":"Feito","evidencia":"e","updated_at":"x",**k}
items=lambda *l: {"updated_at":"x","items":list(l)}
P=3351
def run(name, port, keep=True, **kw):
    d=make(name, **kw); p=start(d, port, keep_path=keep)
    try:
        raw=get(port)
        try: data=json.loads(raw); valid=True
        except Exception: data=json.loads(raw, parse_constant=lambda c: f"<<{c}>>"); valid=False
        return d,raw,data,valid
    finally: p.terminate()
d,raw,data,v=run("a1",P,gh="none",maestri="none",keep=False)
print("A1 gh/maestri ausentes: json_valido",v,"prs",{k:data["prs"][k] for k in ("available","error")},"agents",{k:data["agents"][k] for k in ("available","error")},"tests",data["tests"]["error"],"overall",round(data["overall_percent"],1))
d,raw,data,v=run("a2",P+1,gh="fail"); print("A2 gh 401: prs.error=",data["prs"]["error"],"| token no json:", "ghp_FAKE" in raw, "| tests.error:", data["tests"]["error"])
for nm,ck in (("vazio",items()),("lista",[]),("json invalido","{not json"),("texto","hello")):
    d,raw,data,v=run("a3",P+2,checklist=ck); print(f"A3 checklist {nm}: overall={data['overall_percent']} checklist_error={data.get('checklist_error')!r} n={data['checklist']['progress']['n_items']}")
for nm,l in (("peso 1e999",[it("a",peso=1e999),it("b",estado="Pendente")]),("peso NaN str",[it("a",peso="NaN"),it("b")]),("peso 0",[it("a",peso=0),it("b",peso=0,estado="Pendente")]),("100%",[it("a",peso=3),it("b")]),("0%",[it("a",estado="Pendente"),it("b",estado="Bloqueado")]),("estados novos",[it("a",estado="concluida"),it("b",estado="devolvida"),it("c",estado="em_correcao (ciclo 2)"),it("d",estado=None)])):
    d,raw,data,v=run("a4",P+3,checklist=items(*l)); print(f"A4 {nm}: json_valido={v} overall={data.get('overall_percent')} counts={data['checklist']['progress'].get('state_counts')} erro={data.get('checklist_error')!r}")
d,raw,data,v=run("a5",P+4,tasks="# T\n|ID|T|R|S|A|\n|---|---|---|---|---|\n| T1 | so | 3 |\n| T3 | tarefa com \\| pipe | r | concluida | ok |\n| <script>x</script> | a | b | c | d |\n")
print("A5 TASKS:", [(t["id"],t["status"]) for t in data["tasks"]])
d,raw,data,v=run("a6",P+5,status="# STATUS\n## Bloqueios\n- chave OPENROUTER_API_KEY=sk-or-v1-FAKE\n## Próximos passos\n- x\n")
print("A6 STATUS raw no json:", "sk-or-v1-FAKE" in raw, "| chaves status:", list(data["status"].keys()), "| agents chaves:", list(data["agents"].keys()), "| maestri token no json:", "sk-FAKE-SECRET-123" in raw)
d,raw,data,v=run("a7",P+6); print("A7 CI vermelho: tests=", {k:data["tests"][k] for k in ("passed","failed","error")}, "ci=", data["tests"]["last_ci_main"]["conclusion"])
