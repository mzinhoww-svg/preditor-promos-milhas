import sys, os, json, shutil, subprocess, time, textwrap, pathlib, urllib.request
S=os.environ["S"]; SRC=S+"/wt21"
def make(name, checklist=None, tasks=None, status=None, progress=None, gh="ok", maestri="ok", uv="ok", pr_title=None):
    d=pathlib.Path(S)/"painel"/name; shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC, d, ignore=shutil.ignore_patterns(".git","node_modules",".venv","__pycache__"))
    if checklist is not None: (d/"docs/mvp-checklist.json").write_text(checklist if isinstance(checklist,str) else json.dumps(checklist), encoding="utf-8")
    if tasks is not None: (d/"TASKS.md").write_text(tasks, encoding="utf-8")
    if status is not None: (d/"STATUS.md").write_text(status, encoding="utf-8")
    if progress is not None: (d/"docs/progress.json").write_text(progress if isinstance(progress,str) else json.dumps(progress))
    b=d/"bin"; b.mkdir()
    def sh(n, body): (b/n).write_text("#!/bin/bash\n"+body+"\n"); (b/n).chmod(0o755)
    if gh=="ok":
        t=pr_title or "PR normal"
        prs=[{"number":1,"title":t,"state":"OPEN","statusCheckRollup":[{"name":"t","conclusion":"SUCCESS"}],"labels":[{"name":"x"}],"isDraft":False,"updatedAt":"2026-10-13T00:00:00Z","headRefName":"b"}]
        (b/"prs.json").write_text(json.dumps(prs))
        sh("gh", f'if [ "$1" = pr ]; then cat "{b}/prs.json"; else echo "[]"; fi')
    elif gh=="fail": sh("gh","echo 'HTTP 401: Bad credentials (token ghp_FAKEFAKEFAKE)' >&2; exit 1")
    elif gh=="badjson": sh("gh","echo 'not json'")
    elif gh=="hang": sh("gh","sleep 60")
    if maestri=="ok": sh("maestri",'echo \'- name: "Agente <b>X</b>" role: "QA" token=sk-FAKE-SECRET-123\'')
    elif maestri=="fail": sh("maestri","echo boom >&2; exit 2")
    if uv=="ok": sh("uv","echo '12 passed in 0.5s'")
    elif uv=="red": sh("uv","echo '3 failed, 9 passed'; exit 1")
    elif uv=="secret": sh("uv","echo 'ERROR connecting postgresql+psycopg://preditor:S3CRETPW@127.0.0.1/db'; echo '1 passed'")
    # servidor: mesmo codigo do autor, porta 3350+
    return d
def start(d, port, extra_env=None, keep_path=True):
    env=dict(os.environ); env["PATH"]=f"{d}/bin:"+("/usr/bin:/bin" if not keep_path else env["PATH"])
    if extra_env: env.update(extra_env)
    code=textwrap.dedent(f'''
        import sys, threading, time, http.server
        sys.path.insert(0, r"{d}/tools/painel")
        import server as s
        threading.Thread(target=s.recalc_loop, daemon=True).start()
        for _ in range(300):
            if s.STATE.get("data") is not None: break
            time.sleep(0.1)
        http.server.ThreadingHTTPServer(("127.0.0.1", {port}), s.Handler).serve_forever()
    ''')
    p=subprocess.Popen([os.environ["PYSRV"],"-c",code],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,cwd=str(d))
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/data.json",timeout=1); break
        except Exception: time.sleep(0.3)
    return p
def get(port, path="/data.json"):
    return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}",timeout=10).read().decode()
