"""Servidor HTTP do painel de progresso (stdlib only)."""
from __future__ import annotations

import http.server
import json
import re
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKLIST = ROOT / "docs" / "mvp-checklist.json"
TASKS = ROOT / "TASKS.md"
STATUS = ROOT / "STATUS.md"
PROGRESS = ROOT / "docs" / "progress.json"

try:  # package or script
    from .calc import calc_progress  # type: ignore
except Exception:  # noqa: BLE001  # pragma: no cover
    from calc import calc_progress  # type: ignore

LOCK = threading.Lock()
STATE: dict = {"data": None, "updated": 0.0}


def run_cmd(cmd: list[str], timeout: int = 20) -> tuple[str | None, str | None]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT), check=False)
    except FileNotFoundError:
        return None, "comando nao encontrado"
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception as e:  # noqa: BLE001  # pragma: no cover
        return None, str(e)
    if p.returncode != 0:
        return None, (p.stderr or "").strip()[:300]
    return p.stdout, None


def load_json(path: Path) -> object | None:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def parse_md_table(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return rows
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|") or set(s.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [c.strip() for c in s.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[0].lower() in ("id", "tarefa", ""):
            continue
        rows.append({"id": cells[0], "tarefa": cells[1], "responsavel": cells[2], "status": cells[3],
                    "aceite": cells[4] if len(cells) > 4 else ""})
    return rows



_STATUS_SECTIONS_CACHE: dict = {}


def read_status() -> dict:
    text = ""
    try:
        if STATUS.exists():
            text = STATUS.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        text = ""
    # simple heuristics: sections Bloqueios / Próximos passos
    blocks: list[str] = []
    nxt: list[str] = []
    mode = None
    for line in text.splitlines():
        s = line.strip()
        low = s.lower()
        if low.startswith("#") :
            if "bloqueio" in low:
                mode = "blocks"
            elif ("pr" in low and "ximo" in low) or "passo" in low:
                mode = "next"
            else:
                # only reset mode on a new heading that is a major section
                # keep mode if heading matches keywords above; else leave? reset to None for other sections
                if s.startswith(("## ", "# ")) and "bloqueio" not in low and "passo" not in low and "pr" not in low:
                    mode = None
            continue
        if not s:
            continue
        if mode == "blocks":
            blocks.append(s.lstrip("-* ").strip())
        elif mode == "next":
            nxt.append(s.lstrip("-* ").strip())
    if not blocks or not nxt:
        # fallback: include whole text
        pass
    return {"raw": text, "blocks": blocks, "next_steps": nxt}


def collect_prs() -> dict:
    out, err = run_cmd(["gh", "pr", "list", "--state", "all", "--limit", "40",
                        "--json", "number,title,state,statusCheckRollup,labels,isDraft,updatedAt,headRefName"])
    if out is None:
        return {"available": False, "error": err or "gh indisponivel", "open": [], "merged": []}
    try:
        data = json.loads(out)
    except Exception:  # noqa: BLE001
        return {"available": False, "error": "json invalido", "open": [], "merged": []}
    open_prs = []
    merged_prs = []
    for pr in data:
        checks = pr.get("statusCheckRollup") or []
        conclusions = [c.get("conclusion") for c in checks if isinstance(c, dict)]
        if any(c == "FAILURE" or c == "FAILED" or c == "TIMED_OUT" for c in conclusions):
            ci = "fail"
        elif any(c in (None, "PENDING", "QUEUED", "IN_PROGRESS") for c in conclusions) or not conclusions:
            ci = "pending" if conclusions else "unknown"
        elif all(c == "SUCCESS" or c == "NEUTRAL" or c == "SKIPPED" for c in conclusions):
            ci = "pass"
        else:
            ci = "unknown"
        labels = [ (l.get("name") if isinstance(l, dict) else str(l)) for l in (pr.get("labels") or []) ]
        title = pr.get("title") or ""
        title_low = title.lower()
        awaits = (
            ("teste cruzado" in title_low)
            or any("teste" in str(l).lower() or "cross" in str(l).lower() for l in labels)
            or (str(pr.get("state", "")).upper() == "OPEN"
                and ci == "pass"
                and not title_low.startswith("qa ")
                and "reteste" not in title_low)
        )
        item = {
            "number": pr.get("number"),
            "title": title,
            "state": pr.get("state"),
            "ci": ci,
            "checks": [{"name": c.get("name"), "conclusion": c.get("conclusion")} for c in checks if isinstance(c, dict)],
            "labels": labels,
            "is_draft": pr.get("isDraft"),
            "updated_at": pr.get("updatedAt"),
            "awaits_cross_test": awaits,
        }
        if str(pr.get("state", "")).upper() == "OPEN":
            open_prs.append(item)
        else:
            merged_prs.append(item)
    return {"available": True, "open": open_prs, "merged": merged_prs, "error": None}


def collect_agents() -> dict:
    out, err = run_cmd(["maestri", "list"], timeout=15)
    if out is None:
        return {"available": False, "error": err or "maestri indisponivel", "raw": "", "agents": []}
    agents = []
    current = None
    for line in out.splitlines():
        s = line.strip()
        m = re.search(r'name:\s*"([^"]+)"', s)
        if m:
            current = {"name": m.group(1), "role": "", "raw": s}
            # try role on same line
            mr = re.search(r'role:\s*"([^"]*)"', s)
            if mr:
                current["role"] = mr.group(1)
            agents.append(current)
        elif current is not None and "role:" in s:
            mr = re.search(r'role:\s*"([^"]*)"', s)
            if mr:
                current["role"] = mr.group(1)
    return {"available": True, "error": None, "raw": out, "agents": agents}


def collect_tests() -> dict:
    # pytest (best-effort, timeout)
    cmd = ["uv", "run", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"]
    out, err = run_cmd(cmd, timeout=120)
    passed = None
    failed = None
    tail = ""
    if out is not None:
        tail = "\n".join((out or "").splitlines()[-8:])
        m = re.search(r"(\d+)\s+passed", out or "")
        if m:
            passed = int(m.group(1))
        m2 = re.search(r"(\d+)\s+failed", out or "")
        if m2:
            failed = int(m2.group(1))
    # last CI on main
    ci_out, _ = run_cmd(["gh", "run", "list", "--branch", "main", "--limit", "1",
                              "--json", "status,conclusion,name,updatedAt,headSha"], timeout=20)
    last_ci = None
    if ci_out is not None:
        try:
            arr = json.loads(ci_out)
            if arr:
                last_ci = arr[0]
        except Exception:  # noqa: BLE001
            last_ci = None
    return {
        "pytest": {"available": out is not None, "passed": passed, "failed": failed,
                   "error": None if out is not None else (err or "pytest indisponivel"), "tail": tail},
        "last_ci_main": last_ci,
    }


def extract_budget(obj: object) -> dict:
    spent = None
    cap = None
    percent = None

    def search(o: object):
        nonlocal spent, cap, percent
        if isinstance(o, dict):
            for k, v in o.items():
                kl = str(k).lower()
                if spent is None and kl in ("spent_brl", "spent", "gasto", "gasto_brl", "gasto_reais", "amount_brl", "amount") and isinstance(v, (int, float)):
                    spent = float(v)
                if cap is None and kl in ("cap_brl", "cap", "teto", "teto_brl", "budget_cap_brl", "budget_cap") and isinstance(v, (int, float)):
                    cap = float(v)
                if percent is None and kl in ("percent", "pct", "percentual") and isinstance(v, (int, float)):
                    percent = float(v)
                search(v)
        elif isinstance(o, list):
            for it in o:
                search(it)

    search(obj)
    if cap is None:
        cap = 100.0
    if spent is None:
        spent = 0.0
    if percent is None and cap:
        percent = (spent / cap) * 100.0
    return {"spent_brl": spent, "cap_brl": cap, "percent": percent, "provider": "openrouter"}


def build_data() -> dict:
    now = datetime.now(UTC).isoformat()
    ck = load_json(CHECKLIST)
    prog = load_json(PROGRESS)

    calc = calc_progress(ck)
    # attach checklist meta
    if isinstance(ck, dict):
        calc["updated_at"] = ck.get("updated_at")

    phases_pct = calc.get("by_phase_pct", calc.get("by_phase", {}))
    # ensure canonical phases
    tasks = parse_md_table(TASKS)
    prs = collect_prs()
    agents = collect_agents()
    # enriquece agentes com tarefas atuais
    for a in agents.get("agents", []):
        name = (a.get("name") or "").lower()
        matches = []
        for t in tasks:
            resp = str(t.get("responsavel", "")).lower()
            if name and name in resp:
                matches.append(t)
        a["tasks"] = [t.get("tarefa") for t in matches]
        a["current_task"] = (matches[0].get("tarefa") if matches else None)
        a["task_count"] = len(matches)
    tests = collect_tests()
    status = read_status()
    budget = extract_budget(prog if prog is not None else {})

    # agent enrichment: append task summary counts
    task_counts: dict[str, dict] = {}
    for t in tasks:
        r = t.get("responsavel", "")
        task_counts.setdefault(r, {"total": 0, "done": 0})
        task_counts[r]["total"] += 1
        if "conclu" in str(t.get("status", "")).lower():
            task_counts[r]["done"] += 1

    return {
        "generated_at": now,
        "overall": calc.get("overall", 0.0),
        "overall_percent": calc.get("overall_percent", 0.0),
        "phases": phases_pct,
        "phases_ratio": calc.get("by_phase", {}),
        "checklist": {
            "items": calc.get("items", []),
            "progress": calc,
            "raw": ck,
        },
        "tasks": tasks,
        "task_counts": task_counts,
        "prs": prs,
        "agents": agents,
        "tests": tests,
        "budget": budget,
        "status": status,
    }


def recalc_loop() -> None:
    while True:
        try:
            new = build_data()
        except Exception as e:  # noqa: BLE001  # pragma: no cover
            new = {"generated_at": datetime.now(UTC).isoformat(), "error": str(e)}
        with LOCK:
            STATE["data"] = new
            STATE["updated"] = time.time()
        time.sleep(15)


HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel de Progresso - MVP</title>
<style>
:root{--bg:#ffffff;--fg:#111;--muted:#555;--card:#f4f4f5;--dark:#1a1a1a;--accent:#0b5ed7;--done:#16803d;--rev:#b45309;--prog:#2563eb;--pend:#6b7280;--block:#dc2626;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:18px;line-height:1.3}
.wrap{max-width:1500px;margin:0 auto;padding:24px}
h1{font-size:40px;margin:0 0 8px}
h2{font-size:24px;margin:22px 0 10px}
.sub{color:var(--muted);font-size:16px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}
.card{background:var(--card);border-radius:14px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card.dark{background:var(--dark);color:#fff}
.span-12{grid-column:span 12}
.span-6{grid-column:span 6}
.span-4{grid-column:span 4}
.span-3{grid-column:span 3}
.num{font-size:72px;font-weight:800;line-height:1}
.bar{height:28px;background:#e5e7eb;border-radius:14px;overflow:hidden}
.bar>div{height:100%;background:var(--accent);transition:width .5s}
.phase{margin:10px 0}
.phase .label{display:flex;justify-content:space-between;font-size:18px;font-weight:600}
.phase .bar{height:16px}
.item{display:grid;grid-template-columns:90px 1fr 180px 220px 150px;gap:8px;align-items:center;padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:16px}
.item:last-child{border-bottom:none}
.badge{display:inline-block;padding:4px 10px;border-radius:999px;color:#fff;font-size:14px;font-weight:700;white-space:nowrap}
.b-Feito{background:var(--done)}
.b-Em\ revisao{background:var(--rev)}
.b-Em\ andamento{background:var(--prog)}
.b-Pendente{background:var(--pend)}
.b-Bloqueado{background:var(--block)}
.b-Desconhecido{background:var(--pend)}
.pr{padding:10px 0;border-bottom:1px solid #e5e7eb}
.ci{font-size:14px;font-weight:700}
.ci.pass{color:var(--done)}
.ci.fail{color:var(--block)}
.ci.pending{color:var(--rev)}
.ci.unknown{color:var(--pend)}
ul{margin:8px 0;padding-left:20px}
li{margin:4px 0}
table{width:100%;border-collapse:collapse}
td,th{padding:6px 8px;border-bottom:1px solid #e5e7eb;font-size:15px;text-align:left}
@media (max-width:1100px){.span-6,.span-4,.span-3{grid-column:span 12}.item{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<h1>Painel de progresso - MVP</h1>
<div class="sub">Atualiza a cada 5s (dados recalculados a cada 15s). Fonte: docs/mvp-checklist.json + TASKS.md + GitHub. Gasto: OpenRouter teto R$ 100.</div>

<div class="grid">
  <div class="card dark span-4">
    <div style="font-size:20px;font-weight:700;margin-bottom:6px">Progresso geral do MVP</div>
    <div class="num" id="overallNum">--%</div>
    <div class="bar" style="margin-top:10px;background:#333"><div id="overallBar" style="background:#4ade80"></div></div>
    <div id="overallCounts" style="margin-top:8px;font-size:15px;color:#ddd"></div>
    <div id="overallMeta" style="margin-top:4px;font-size:14px;color:#ccc"></div>
    <div id="overallNote" style="margin-top:6px;font-size:14px;color:#bbb">o percentual mede itens do MVP, nao tempo</div>
  </div>
  <div class="card span-4">
    <div style="font-size:20px;font-weight:700;margin-bottom:6px">Testes</div>
    <div style="font-size:46px;font-weight:800" id="testsNum">--</div>
    <div style="font-size:16px;color:var(--muted)">passando</div>
    <div style="margin-top:8px;font-size:15px" id="testsDetail"></div>
  </div>
  <div class="card span-4">
    <div style="font-size:20px;font-weight:700;margin-bottom:6px">Orçamento</div>
    <div style="font-size:46px;font-weight:800" id="budgetNum">--</div>
    <div style="font-size:16px;color:var(--muted)">gasto de R$ 100</div>
    <div class="bar" style="margin-top:10px"><div id="budgetBar"></div></div>
    <div id="budgetDetail" style="margin-top:6px;font-size:14px;color:var(--muted)"></div>
  </div>
</div>

<div class="grid" style="margin-top:16px">
  <div class="card span-6">
    <h2 style="margin-top:0">Progresso por fase</h2>
    <div id="phases"></div>
  </div>
  <div class="card span-6">
    <h2 style="margin-top:0">Bloqueios e próximos passos</h2>
    <div style="font-weight:700;margin-bottom:4px">Bloqueios</div>
    <ul id="blocks"></ul>
    <div style="font-weight:700;margin:10px 0 4px">Próximos passos</div>
    <ul id="nexts"></ul>
  </div>
</div>

<div class="card span-12" style="margin-top:16px">
  <h2 style="margin-top:0">Checklist do MVP</h2>
  <div id="items"></div>
</div>

<div class="grid" style="margin-top:16px">
  <div class="card span-6">
    <h2 style="margin-top:0">Pull requests</h2>
    <div style="font-weight:700;margin-bottom:6px">Abertos</div>
    <div id="prsOpen"></div>
    <div style="font-weight:700;margin:14px 0 6px">Mergeados</div>
    <div id="prsMerged"></div>
  </div>
  <div class="card span-6">
    <h2 style="margin-top:0">Agentes e tarefas</h2>
    <div id="agents"></div>
    <div style="font-weight:700;margin:14px 0 6px">Tarefas (TASKS.md)</div>
    <div id="tasks"></div>
  </div>
</div>

<div class="card span-12" style="margin-top:16px">
  <h2 style="margin-top:0">Último CI da main</h2>
  <div id="lastCi"></div>
</div>

</div>
<script>
const STATE_COLOR={"Feito":"done","Em revisao":"rev","Em andamento":"prog","Pendente":"pend","Bloqueado":"block","Desconhecido":"pend"};
const STATE_TEXT={"Feito":"Feito","Em revisao":"Em revisao","Em andamento":"Em andamento","Pendente":"Pendente","Bloqueado":"Bloqueado","Desconhecido":"Desconhecido"};
const PHASES=["Setup","Portao de viabilidade/coleta","Estruturacao/extrator","Modelo","Produto/dashboard/API/deploy","Seguranca e custo"];

async function load(){
  try{
    const r=await fetch('/data.json',{cache:'no-store'});
    const d=await r.json();
    render(d);
  }catch(e){console.error(e);}
}
function render(d){
  const op=d.overall_percent||0;
  document.getElementById('overallNum').textContent=Math.round(op)+'%';
  document.getElementById('overallBar').style.width=op+'%';
  const sc=d.checklist?.progress?.state_counts||{};
  document.getElementById('overallCounts').textContent='Feito: '+(sc.Feito||0)+' · Em revisao: '+(sc['Em revisao']||0)+' · Em andamento: '+(sc['Em andamento']||0)+' · Pendente: '+(sc.Pendente||0)+' · Bloqueado: '+(sc.Bloqueado||0);
  document.getElementById('overallMeta').textContent='Itens: '+(d.checklist?.progress?.n_items||0)+' | peso: '+((d.checklist?.progress?.total_weight||0).toFixed(1));
  // tests
  const t=d.tests?.pytest||{};
  const passed=t.passed;
  document.getElementById('testsNum').textContent=(passed===null?'--':passed);
  document.getElementById('testsDetail').innerHTML='falhando: '+(t.failed??'?')+'<br>'+ (d.tests?.last_ci_main?('ultimo CI main: '+ (d.tests.last_ci_main.conclusion||d.tests.last_ci_main.status)):'');
  // budget
  const b=d.budget||{};
  document.getElementById('budgetNum').textContent='R$ '+ (b.spent_brl||0).toFixed(2);
  const bp=(b.percent||0);
  document.getElementById('budgetBar').style.width=Math.min(100,bp)+'%';
  document.getElementById('budgetDetail').textContent='teto R$ '+(b.cap_brl||100).toFixed(2)+' ('+bp.toFixed(1)+'%)';
  // phases
  const ph=d.phases||{};
  let phHtml='';
  for(const p of PHASES){
    const val=(ph[p]!==undefined?ph[p]:0);
    const num=typeof val==='number'?(val<=1?val*100:val):0;
    phHtml+='<div class="phase"><div class="label"><span>'+p+'</span><span>'+Math.round(num)+'%</span></div><div class="bar"><div style="width:'+num+'%"></div></div></div>';
  }
  document.getElementById('phases').innerHTML=phHtml;
  // items
  const items=d.checklist?.items||[];
  let itHtml='';
  for(const it of items){
    const st=it.estado||'Pendente';
    const cls='b-'+st.replace(/ /g,'\\ ');
    itHtml+='<div class="item">'+
      '<div style="font-weight:700">'+(it.id||'')+'</div>'+
      '<div>'+(it.title||'')+'<div style="font-size:13px;color:var(--muted)">'+(it.fase||'')+' &middot; peso '+(it.peso??'')+'</div></div>'+
      '<div><span class="badge '+cls+'">'+st+'</span></div>'+
      '<div style="font-size:14px">'+(it.evidencia||'')+'</div>'+
      '<div style="font-size:14px;color:var(--muted)">'+(it.updated_at||'')+'</div>'+
    '</div>';
  }
  document.getElementById('items').innerHTML=itHtml || '<div style="color:var(--muted)">sem itens</div>';
  // PRs
  function prCard(p){
    const ci=p.ci||'unknown';
    const cross=p.awaits_cross_test?' &middot; aguarda teste cruzado':'';
    return '<div class="pr"><div style="font-weight:700">#'+p.number+' '+ (p.title||'') +'</div>'+
      '<div style="font-size:14px;color:var(--muted)">CI: <span class="ci '+ci+'">'+ci+'</span>'+cross+' &middot; '+(p.state||'')+'</div></div>';
  }
  document.getElementById('prsOpen').innerHTML=(d.prs?.open||[]).map(prCard).join('')||'<div style="color:var(--muted)">nehum</div>';
  document.getElementById('prsMerged').innerHTML=(d.prs?.merged||[]).map(prCard).join('')||'<div style="color:var(--muted)">nehum</div>';
  // agents
  const agents=d.agents?.agents||[];
  let agHtml='<ul>';
  for(const a of agents){
    const ct=a.current_task || (a.tasks||[]).join(', ');
    agHtml+='<li><b>'+ (a.name||'') +'</b> '+(a.role?'('+a.role+')':'')+(ct?' — '+ct:'')+'</li>';
  }
  agHtml+='</ul>';
  if(d.agents?.available===false){agHtml='<div style="color:var(--muted)">'+(d.agents.error||'maestri indisponivel')+'</div>';}
  document.getElementById('agents').innerHTML=agHtml;
  // tasks
  const tasks=d.tasks||[];
  let tHtml='<table><thead><tr><th>ID</th><th>Tarefa</th><th>Responsável</th><th>Status</th></tr></thead><tbody>';
  for(const t of tasks){
    tHtml+='<tr><td>'+ (t.id||'') +'</td><td>'+ (t.tarefa||'') +'</td><td>'+ (t.responsavel||'') +'</td><td>'+ (t.status||'') +'</td></tr>';
  }
  tHtml+='</tbody></table>';
  document.getElementById('tasks').innerHTML=tHtml;
  // status
  const blocks=d.status?.blocks||[];
  const nexts=d.status?.next_steps||[];
  document.getElementById('blocks').innerHTML=blocks.map(x=>'<li>'+x+'</li>').join('')||'<li style="color:var(--muted)">n/a</li>';
  document.getElementById('nexts').innerHTML=nexts.map(x=>'<li>'+x+'</li>').join('')||'<li style="color:var(--muted)">n/a</li>';
  // last ci
  const ci=d.tests?.last_ci_main;
  if(ci){
    document.getElementById('lastCi').innerHTML='<div style="font-size:20px;font-weight:700">'+(ci.conclusion||ci.status||'--')+'</div><div style="color:var(--muted);font-size:15px">'+(ci.name||'')+' &middot; '+ (ci.updatedAt||'') +'</div>';
  }else{
    document.getElementById('lastCi').textContent='indisponivel';
  }
}
load();
setInterval(load,5000);
</script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            b = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif path == "/data.json":
            with LOCK:
                data = STATE.get("data")
            if data is None:
                data = {"error": "calculando", "generated_at": None}
            b = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # silence
        return


def main() -> None:
    # initial compute
    t = threading.Thread(target=recalc_loop, daemon=True)
    t.start()
    # wait first
    for _ in range(50):
        with LOCK:
            if STATE.get("data") is not None:
                break
        time.sleep(0.1)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 3300), Handler)
    print("Painel em http://127.0.0.1:3300", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
