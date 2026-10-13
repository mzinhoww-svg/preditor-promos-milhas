import os, json, shutil, subprocess, time, pathlib, urllib.request, sys
S=os.environ["S"]; SRC=S+"/wt21b"; PY=os.environ["PYSRV"]
def make(name, checklist=None, tasks=None, status=None, progress=None, gh="ok", maestri="ok", pr_title=None, ci="red"):
    d=pathlib.Path(S)/"painel"/name; shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC, d, ignore=shutil.ignore_patterns(".git","node_modules",".venv","__pycache__"))
    if checklist is not None: (d/"docs/mvp-checklist.json").write_text(checklist if isinstance(checklist,str) else json.dumps(checklist), encoding="utf-8")
    if tasks is not None: (d/"TASKS.md").write_text(tasks, encoding="utf-8")
    if status is not None: (d/"STATUS.md").write_text(status, encoding="utf-8")
    b=d/"bin"; b.mkdir(); mark=d/"MARK.log"
    def sh(n, body): (b/n).write_text("#!/bin/bash\n"+body+"\n"); (b/n).chmod(0o755)
    sh("uv", f'echo "uv $@" >> "{mark}"; exit 1'); sh("pytest", f'echo "pytest $@" >> "{mark}"; exit 1'); sh("python3-pytest", "true")
    prs=[{"number":1,"title":pr_title or "PR normal","state":"OPEN","statusCheckRollup":[{"name":"t","conclusion":"SUCCESS"}],"labels":[{"name":"x"}],"isDraft":False,"updatedAt":"2026-10-13T00:00:00Z","headRefName":"b"}]
    (b/"prs.json").write_text(json.dumps(prs))
    runs=[{"databaseId":99,"status":"completed","conclusion":"failure" if ci=="red" else "success","name":"ci","updatedAt":"2026-10-13T00:00:00Z","headSha":"abc","workflowName":"ci"}]
    (b/"runs.json").write_text(json.dumps(runs))
    if gh=="ok":
        sh("gh", f'echo "gh $@" >> "{mark}"\nif [ "$1" = pr ]; then cat "{b}/prs.json"; elif [ "$1 $2" = "run list" ]; then cat "{b}/runs.json"; elif [ "$1 $2" = "run view" ]; then echo "tests: 3 failed, 9 passed in 1s"; else echo "[]"; fi')
    elif gh=="fail": sh("gh","echo 'HTTP 401: Bad credentials (token ghp_FAKEFAKEFAKE)' >&2; exit 1")
    if maestri=="ok": sh("maestri",'echo \'- name: "Agente <b>X</b>" role: "QA" token=sk-FAKE-SECRET-123\'')
    return d
def start(d, port, extra_env=None, keep_path=True):
    env=dict(os.environ); env["PATH"]=f"{d}/bin:"+(env["PATH"] if keep_path else "/usr/bin:/bin"); env["PAINEL_PORT"]=str(port)
    if extra_env: env.update(extra_env)
    p=subprocess.Popen([PY,"tools/painel/server.py"],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,cwd=str(d))
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/data.json",timeout=1); break
        except Exception: time.sleep(0.3)
    return p
def get(port, path="/data.json"): return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}",timeout=10).read().decode()
