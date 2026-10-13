import os, json, time, re, subprocess, urllib.request
from harness3 import *
X='<img src=x onerror="window.__xss=(window.__xss||0)+1;document.title=\'XSSED\'">'
it=lambda i,**k: {"id":i,"title":"t "+i,"fase":"Setup","peso":1,"estado":"Feito","evidencia":"e","updated_at":"x",**k}
def fetch(port):
    try:
        raw=urllib.request.urlopen(f"http://127.0.0.1:{port}/data.json",timeout=6).read().decode(); return json.loads(raw), raw
    except Exception as e: return None, f"EXC {type(e).__name__}"
res={}
d=make("z0"); p=start(d,3401); time.sleep(1)
h=get(3401,"/"); js=re.search(r"<script>(.*)</script>",h,re.S).group(1); open("page_ok.js","w").write(js)
r=subprocess.run(["node","--check","page_ok.js"],capture_output=True,text=True); print("node --check:", "ok" if r.returncode==0 else r.stderr[:200])
data,raw=fetch(3401); print("real: overall", round(data["overall_percent"],1), "tests", {k:data["tests"][k] for k in ("passed","failed","error")}, "MARK:", [l.split()[0] for l in open(d/"MARK.log").read().splitlines()][:6])
cases={"inf":[it("a",peso=1e999),it("b",estado="Pendente")], "nondict":[1,"x",None,it("ok")], "xss":[it("a",title="i "+X,evidencia=X),it("b",estado="Pendente",fase=X)], "str peso nan":[it("a",peso="NaN"),it("b")], "estados":[it("a",estado="concluida"),it("b",estado="devolvida"),it("c",estado=None)]}
ports={}
for i,(nm,l) in enumerate(cases.items()):
    kw={"checklist":{"updated_at":"x","items":l}}
    if nm=="xss": kw.update(pr_title="PR "+X, tasks="# T\n|ID|T|R|S|A|\n|---|---|---|---|---|\n| "+X+" | t | r | concluida | a |\n", status="# S\n## Bloqueios\n- "+X+"\n## Próximos passos\n- <script>window.__xss=99</script>\n")
    dd=make("z"+str(i+1),**kw); port=3402+i; start(dd,port); ports[nm]=port
time.sleep(3)
for nm,port in ports.items():
    data,raw=fetch(port)
    if data is None: print(f"{nm}: {raw}"); continue
    print(f"{nm}: overall={data.get('overall_percent')} n_items={data['checklist']['progress']['n_items']} erro={data.get('checklist_error')} counts={data['checklist']['progress'].get('state_counts')} raw_tipo={type(data['checklist'].get('raw')).__name__}")
# CI verde/vermelho + gh ausente
json.dump(ports, open("ports_rt.json","w"))
