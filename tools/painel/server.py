"""Servidor HTTP do painel de progresso (stdlib only)."""
from __future__ import annotations

import http.server
import json
import os
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
REFRESH_LOCK = threading.Lock()
LAST_REFRESH_TS = 0.0


def run_cmd(cmd: list[str], timeout: int = 20) -> tuple[str | None, str | None]:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT), check=False, env=env)
    except FileNotFoundError:
        return None, "comando indisponivel"
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception:  # noqa: BLE001  # pragma: no cover
        return None, "erro"
    if p.returncode != 0:
        return None, "falha"
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
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", s.strip().strip("|"))]
        if len(cells) < 4 or all(not c for c in cells):
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
    return {"blocks": blocks, "next_steps": nxt}


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
    return {"available": True, "error": None, "agents": agents}


def collect_ci_main() -> tuple[dict | None, str | None]:
    out, err = run_cmd(
        ["gh", "run", "list", "--branch", "main", "--limit", "1",
         "--json", "databaseId,status,conclusion,name,updatedAt,headSha,workflowName"],
        timeout=30,
    )
    if out is None:
        return None, err or "indisponivel"
    try:
        arr = json.loads(out)
    except Exception:  # noqa: BLE001
        return None, "json invalido"
    if not isinstance(arr, list) or not arr:
        return None, "sem runs"
    run = arr[0]
    run_id = run.get("databaseId")
    passed = None
    failed = None
    if run_id is not None:
        log_out, _ = run_cmd(["gh", "run", "view", str(run_id), "--log"], timeout=45)
        if log_out:
            matches = list(re.finditer(r"(\d+)\s+passed", log_out))
            if matches:
                passed = int(matches[-1].group(1))
            matches_f = list(re.finditer(r"(\d+)\s+failed", log_out))
            if matches_f:
                failed = int(matches_f[-1].group(1))
    run = dict(run)
    run["passed"] = passed
    run["failed"] = failed
    return run, None


def collect_tests() -> dict:
    run, err = collect_ci_main()
    passed = run.get("passed") if isinstance(run, dict) else None
    failed = run.get("failed") if isinstance(run, dict) else None
    return {
        "passed": passed,
        "failed": failed,
        "error": err,
        "last_ci_main": run,
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
    checklist_error = calc.get("checklist_error") or calc.get("error")
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
        },
        "checklist_error": checklist_error,
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
:root{--bg:#ffffff;--fg:#111;--muted:#555;--card:#f4f4f5;--dark:#1a1a1a;--accent:#0b5ed7;--done:#16803d;--rev:#b45309;--prog:#2563eb;--pend:#6b7280;--block:#dc2626;--err:#991b1b;--errbg:#fee2e2}
button.refresh{padding:8px 14px;border:none;border-radius:10px;background:var(--accent);color:#fff;font-weight:700;cursor:pointer}
button.refresh:disabled{opacity:.6;cursor:not-allowed}
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
.b-Em-revisao{background:var(--rev)}
.b-Em-andamento{background:var(--prog)}
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
.banner{display:none;background:var(--errbg);color:var(--err);padding:12px 16px;border-radius:10px;margin:0 0 16px;font-weight:700}
@media (max-width:1100px){.span-6,.span-4{grid-column:span 12}.item{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<div id="errorBanner" class="banner"></div>
<h1>Painel de progresso - MVP</h1>
<div class="sub">Atualiza a cada 5s (dados recalculados a cada 15s). Fonte: docs/mvp-checklist.json + TASKS.md + GitHub. Gasto: OpenRouter teto R$ 100.</div>
<div style="margin:0 0 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
  <button id="refreshBtn" class="refresh" type="button">Atualizar agora</button>
  <span id="refreshStatus" style="color:var(--muted);font-size:15px"></span>
  <span id="generatedAt" style="color:var(--muted);font-size:15px"></span>
  <span id="elapsed" style="color:var(--muted);font-size:15px"></span>
</div>

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
    <div style="font-size:20px;font-weight:700;margin-bottom:6px">Testes / CI da main</div>
    <div style="font-size:46px;font-weight:800" id="testsNum">--</div>
    <div style="font-size:16px;color:var(--muted)">ultimo CI</div>
    <div style="margin-top:8px;font-size:15px" id="testsDetail"></div>
  </div>
  <div class="card span-4">
    <div style="font-size:20px;font-weight:700;margin-bottom:6px">Orcamento</div>
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
    <h2 style="margin-top:0">Bloqueios e proximos passos</h2>
    <div style="font-weight:700;margin-bottom:4px">Bloqueios</div>
    <ul id="blocks"></ul>
    <div style="font-weight:700;margin:10px 0 4px">Proximos passos</div>
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
  <h2 style="margin-top:0">Ultimo CI da main</h2>
  <div id="lastCi"></div>
</div>

</div>
<script>
const PHASES=["Setup","Portao de viabilidade/coleta","Estruturacao/extrator","Modelo","Produto/dashboard/API/deploy","Seguranca e custo"];
let lastGeneratedMs=0;
function showError(msg){
  const b=document.getElementById('errorBanner');
  b.style.display='block';
  b.textContent=msg;
}
function mk(tag, cls){const e=document.createElement(tag); if(cls) e.className=cls; return e;}
function txt(parent, value){ parent.textContent = (value===null||value===undefined)?'':String(value); return parent; }
function append(parent, child){ parent.appendChild(child); return parent; }

async function load(){
  let d=null;
  try{
    const r=await fetch('/data.json',{cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    d=await r.json();
  }catch(e){
    showError('data.json invalido ou inacessivel: '+e.message);
    return;
  }
  const banner=document.getElementById('errorBanner');
  banner.style.display='none';
  if(d && (d.error || d.checklist_error)){
    showError('Erro: '+(d.error||d.checklist_error));
  }
  render(d||{});
  if(d && d.generated_at){
    lastGeneratedMs=Date.parse(d.generated_at);
    const ga=document.getElementById('generatedAt');
    if(ga && !isNaN(lastGeneratedMs)) ga.textContent='gerado em '+new Date(lastGeneratedMs).toLocaleTimeString();
  }
}
function render(d){
  const op = (typeof d.overall_percent === 'number' && isFinite(d.overall_percent)) ? d.overall_percent : null;
  document.getElementById('overallNum').textContent = (op===null?'--':Math.round(op)+'%');
  document.getElementById('overallBar').style.width = (op===null?0:op)+'%';
  const sc=d.checklist?.progress?.state_counts||d.checklist?.progress?.counts||{};
  document.getElementById('overallCounts').textContent='Feito: '+(sc.Feito||0)+' · Em revisao: '+(sc['Em revisao']||0)+' · Em andamento: '+(sc['Em andamento']||0)+' · Pendente: '+(sc.Pendente||0)+' · Bloqueado: '+(sc.Bloqueado||0);
  document.getElementById('overallMeta').textContent='Itens: '+(d.checklist?.progress?.n_items||0)+' | peso: '+((d.checklist?.progress?.total_weight||0).toFixed?((d.checklist.progress.total_weight||0).toFixed(1)):(d.checklist?.progress?.total_weight||0));
  // tests
  const t=d.tests||{};
  const lastCi=d.tests?.last_ci_main||t.last_ci_main||null;
  const passed=(typeof t.passed==='number')?t.passed:(t.ci?.passed);
  const testsNumEl=document.getElementById('testsNum');
  if(lastCi && lastCi.conclusion && lastCi.conclusion!=='success'){
    testsNumEl.textContent='FAIL';
    testsNumEl.style.color='var(--block)';
  } else {
    testsNumEl.style.color='';
    testsNumEl.textContent=(passed===undefined||passed===null?'--':passed);
  }
  const detail=document.getElementById('testsDetail');
  detail.textContent='';
  const ci=d.tests?.last_ci_main||t.last_ci_main||null;
  if(ci){
    const line=mk('div'); line.textContent='ultimo CI main: '+(ci.conclusion||ci.status||'--')+' · '+(ci.name||'')+' · '+(ci.updatedAt||'');
    detail.appendChild(line);
  }
  if(t.error){ const e=mk('div'); e.textContent=t.error; detail.appendChild(e); }
  // budget
  const b=d.budget||{};
  document.getElementById('budgetNum').textContent='R$ '+((b.spent_brl||0).toFixed? (b.spent_brl||0).toFixed(2): (b.spent_brl||0));
  const bp=(typeof b.percent==='number' && isFinite(b.percent))? b.percent : 0;
  document.getElementById('budgetBar').style.width=Math.min(100,bp)+'%';
  document.getElementById('budgetDetail').textContent='teto R$ '+((b.cap_brl||100).toFixed? (b.cap_brl||100).toFixed(2): (b.cap_brl||100))+' ('+bp.toFixed(1)+'%)';
  // phases
  const ph=d.phases||{};
  const phasesDiv=document.getElementById('phases');
  phasesDiv.textContent='';
  for(const p of PHASES){
    const val=ph[p];
    const num=(typeof val==='number' && isFinite(val))?(val<=1?val*100:val):0;
    const wrap=mk('div','phase');
    const label=mk('div','label');
    const left=mk('span'); left.textContent=p;
    const right=mk('span'); right.textContent=Math.round(num)+'%';
    append(label,left); append(label,right);
    const bar=mk('div','bar'); const fill=mk('div'); fill.style.width=num+'%'; bar.appendChild(fill);
    append(wrap,label); append(wrap,bar);
    phasesDiv.appendChild(wrap);
  }
  // items
  const itemsDiv=document.getElementById('items');
  itemsDiv.textContent='';
  const items = (d.checklist && Array.isArray(d.checklist.items)) ? d.checklist.items : [];
  if(d.checklist_error){
    const e=mk('div'); e.style.color='var(--err)'; e.textContent='Checklist invalido: '+d.checklist_error; itemsDiv.appendChild(e);
  }
  for(const it of items){
    const st=it.estado||'Pendente';
    const row=mk('div','item');
    const c1=mk('div'); c1.style.fontWeight='700'; c1.textContent=it.id||'';
    const c2=mk('div');
    const title=mk('div'); title.textContent=it.title||'';
    const meta=mk('div'); meta.style.fontSize='13px'; meta.style.color='var(--muted)'; meta.textContent=(it.fase||'')+' · peso '+(it.peso??'');
    append(c2,title); append(c2,meta);
    const c3=mk('div'); const badge=mk('span','badge b-'+String(st).replace(/ /g,'-')); badge.textContent=st; c3.appendChild(badge);
    const c4=mk('div'); c4.style.fontSize='14px'; c4.textContent=it.evidencia||'';
    const c5=mk('div'); c5.style.fontSize='14px'; c5.style.color='var(--muted)'; c5.textContent=it.updated_at||'';
    [c1,c2,c3,c4,c5].forEach(c=>row.appendChild(c));
    itemsDiv.appendChild(row);
  }
  if(!items.length && !d.checklist_error){ const e=mk('div'); e.style.color='var(--muted)'; e.textContent='sem itens'; itemsDiv.appendChild(e); }
  // PRs
  function renderPr(container, list){
    container.textContent='';
    const arr=Array.isArray(list)?list:[];
    if(!arr.length){ const e=mk('div'); e.style.color='var(--muted)'; e.textContent='nenhum'; container.appendChild(e); return;}
    for(const p of arr){
      const wrap=mk('div','pr');
      const title=mk('div'); title.style.fontWeight='700'; title.textContent='#'+(p.number||'')+' '+(p.title||'');
      const ci=p.ci||'unknown';
      const cross = p.awaits_cross_test ? ' · aguarda teste cruzado' : '';
      const sub=mk('div'); sub.style.fontSize='14px'; sub.style.color='var(--muted)';
      const ciSpan=mk('span','ci '+ci); ciSpan.textContent=ci;
      sub.textContent='CI: '; sub.appendChild(ciSpan); txt(sub, ' '+ (p.state||'') + cross);
      // rebuild properly:
      sub.textContent='';
      const pref=mk('span'); pref.textContent='CI: '; sub.appendChild(pref);
      sub.appendChild(ciSpan);
      const tail=mk('span'); tail.textContent=' · '+(p.state||'')+cross; sub.appendChild(tail);
      append(wrap,title); append(wrap,sub);
      container.appendChild(wrap);
    }
  }
  renderPr(document.getElementById('prsOpen'), d.prs?.open||[]);
  renderPr(document.getElementById('prsMerged'), d.prs?.merged||[]);
  // agents
  const agentsDiv=document.getElementById('agents');
  agentsDiv.textContent='';
  const agents=(d.agents && Array.isArray(d.agents.agents))?d.agents.agents:[];
  if(d.agents && d.agents.available===false){ const e=mk('div'); e.style.color='var(--muted)'; e.textContent=d.agents.error||'maestri indisponivel'; agentsDiv.appendChild(e);}
  const ul=mk('ul');
  for(const a of agents){
    const ct=a.current_task || (Array.isArray(a.tasks)?a.tasks.join(', '):'');
    const li=mk('li');
    const b=mk('b'); b.textContent=a.name||''; li.appendChild(b);
    const role=a.role?' ('+a.role+')':''; const t=ct?' — '+ct:'';
    li.appendChild(document.createTextNode(role+t));
    ul.appendChild(li);
  }
  agentsDiv.appendChild(ul);
  // tasks
  const tasksDiv=document.getElementById('tasks');
  tasksDiv.textContent='';
  const table=mk('table');
  const thead=mk('thead'); const hr=mk('tr');
  ['ID','Tarefa','Responsavel','Status'].forEach(h=>{const th=mk('th'); th.textContent=h; hr.appendChild(th);});
  thead.appendChild(hr); table.appendChild(thead);
  const tbody=mk('tbody');
  const tasks=Array.isArray(d.tasks)?d.tasks:[];
  for(const t of tasks){
    const tr=mk('tr');
    [t.id,t.tarefa,t.responsavel,t.status].forEach(v=>{const td=mk('td'); td.textContent=(v===null||v===undefined)?'':v; tr.appendChild(td);});
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  tasksDiv.appendChild(table);
  // status
  const blocksDiv=document.getElementById('blocks'); blocksDiv.textContent='';
  const blocks=Array.isArray(d.status?.blocks)?d.status.blocks:[];
  if(!blocks.length){ const li=mk('li'); li.style.color='var(--muted)'; li.textContent='n/a'; blocksDiv.appendChild(li);}
  for(const x of blocks){ const li=mk('li'); li.textContent=x; blocksDiv.appendChild(li);}
  const nextsDiv=document.getElementById('nexts'); nextsDiv.textContent='';
  const nexts=Array.isArray(d.status?.next_steps)?d.status.next_steps:[];
  if(!nexts.length){ const li=mk('li'); li.style.color='var(--muted)'; li.textContent='n/a'; nextsDiv.appendChild(li);}
  for(const x of nexts){ const li=mk('li'); li.textContent=x; nextsDiv.appendChild(li);}
  // last ci
  const lastCiDiv=document.getElementById('lastCi'); lastCiDiv.textContent='';
  const lastCiData = (d.tests&&d.tests.last_ci_main) ? d.tests.last_ci_main : null;
  if(lastCiData){
    const a=mk('div'); a.style.fontWeight='700'; a.textContent=lastCiData.conclusion||lastCiData.status||'--';
    const b=mk('div'); b.style.color='var(--muted)'; b.style.fontSize='15px'; b.textContent=(lastCiData.name||'')+' · '+(lastCiData.updatedAt||'');
    lastCiDiv.appendChild(a); lastCiDiv.appendChild(b);
  } else {
    lastCiDiv.textContent='indisponivel';
  }
}
async function doRefresh(){
  const btn=document.getElementById('refreshBtn');
  const status=document.getElementById('refreshStatus');
  if(!btn) return;
  btn.disabled=true;
  if(status) status.textContent='Atualizando...';
  try{
    const r=await fetch('/refresh',{method:'POST'});
    const d=await r.json().catch(function(){return {};});
    if(!r.ok) throw new Error((d && d.error) ? d.error : ('HTTP '+r.status));
    await load();
    if(status) status.textContent='Atualizado';
  }catch(e){
    if(status) status.textContent='Erro: '+e.message;
  }finally{
    btn.disabled=false;
  }
}
const __refreshBtn=document.getElementById('refreshBtn');
if(__refreshBtn) __refreshBtn.addEventListener('click', doRefresh);
function updateTimes(){
  if(lastGeneratedMs){
    const sec=Math.max(0, Math.round((Date.now()-lastGeneratedMs)/1000));
    const el=document.getElementById('elapsed');
    if(el) el.textContent='atualizado ha '+sec+' s';
  }
}
setInterval(updateTimes,1000);
updateTimes();
load();
setInterval(load,5000);
</script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        path = self.path.split("?")[0]
        if path in ("/refresh", "/refresh/"):
            # serializa refresh e rate limit 1 chamada / 2s
            if not REFRESH_LOCK.acquire(blocking=False):
                self._json(429, {"error": "atualizacao em andamento", "retry_after": 2})
                return
            try:
                global LAST_REFRESH_TS
                now = time.time()
                if now - LAST_REFRESH_TS < 2.0:
                    retry = 2.0 - (now - LAST_REFRESH_TS)
                    self._json(429, {"error": "limite: 1 atualizacao a cada 2s", "retry_after": retry})
                    return
                LAST_REFRESH_TS = now
                try:
                    new = build_data()
                except Exception:  # noqa: BLE001
                    # tenta expor erro sem segredos
                    self._json(500, {"error": "falha ao recalcular"})
                    return
                with LOCK:
                    STATE["data"] = new
                    STATE["updated"] = time.time()
                self._json(200, {"status": "ok", "generated_at": new.get("generated_at")})
            finally:
                REFRESH_LOCK.release()
            return
        self.send_response(404)
        self.end_headers()

    def _json(self, status: int, data: dict) -> None:
        b = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        try:
            self.wfile.write(b)
        except BrokenPipeError:
            pass

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
            try:
                with LOCK:
                    data = STATE.get("data")
                if data is None:
                    data = {"error": "calculando", "generated_at": None}
                try:
                    self._json(200, data)
                except (ValueError, TypeError):
                    self._json(500, {"error": "dados invalidos"})
            except Exception:  # noqa: BLE001
                self._json(500, {"error": "erro ao gerar data.json"})
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
    port = int(os.getenv("PAINEL_PORT", "3300"))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Painel em http://127.0.0.1:{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
