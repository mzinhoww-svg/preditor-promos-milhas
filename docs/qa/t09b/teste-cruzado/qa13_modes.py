import http.server, json, subprocess, sys, threading, time, os, re, html, urllib.request, copy, signal
REAL = "http://127.0.0.1:8055/v1"; KEY = "design-key"
def real(path):
    r = urllib.request.Request(REAL + path, headers={"X-API-Key": KEY}); return json.loads(urllib.request.urlopen(r, timeout=10).read())
BASE = {p: real(p) for p in ("/predictions?limit=50", "/model/metrics", "/source-health", "/prediction-log/accuracy", "/alerts")}
MODE = {"m": "ok"}
def mutate(path, mode):
    p = path.split("?")[0]; d = copy.deepcopy(BASE.get(path if path in BASE else {"/predictions": "/predictions?limit=50"}.get(p, path)))
    if d is None: return None
    if mode == "c1_keep" and p == "/predictions": d["model"]["name"] = "C1"; d["model"]["champion"]["name"] = "C1"
    if mode == "c1_keep" and p == "/model/metrics": d["champion"]["name"] = "C1"
    if mode == "c1_promote" and p == "/model/metrics": d["champion"]["name"] = "C1"; d["comparison"]["decision"] = "promote_challenger"
    if mode == "c1_promote" and p == "/predictions": d["model"]["name"] = "C1"; d["model"]["champion"]["name"] = "C1"
    if mode == "prob_invalid" and p == "/predictions":
        d["items"][0]["windows"]["7"]["probability"] = 1.7; d["items"][1]["windows"]["7"]["probability"] = "0.5"; d["items"][2]["windows"]["30"]["probability"] = -0.2
    if mode == "xss" and p == "/predictions":
        d["items"][0]["pair"]["origin"] = "<img src=x onerror=alert(1)>"; d["items"][1]["pair"]["destination"] = "Smiles\"><script>alert(2)</script>"
    if mode == "empty" and p == "/predictions": d["items"] = []
    if mode == "empty" and p == "/alerts": d["items"] = []
    if mode == "empty" and p == "/source-health": d["sources"] = []
    if mode == "nulls" and p == "/source-health":
        for s in d["sources"]: s["items_new_24h"] = None; s["extraction_rate_7d"] = None; s["last_success_at"] = None
    if mode == "big" and p == "/predictions": d["items"] = [dict(copy.deepcopy(d["items"][0]), rank=i + 1, pair={"origin": f"Prog{i}", "destination": "Smiles"}) for i in range(500)]
    if mode == "missing_field" and p == "/predictions": del d["items"][0]["windows"]
    return d
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        m = MODE["m"]
        if self.headers.get("X-API-Key") != KEY and m != "nokey": 
            self.send_response(401); self.end_headers(); self.wfile.write(b'{"error":{"code":"unauthorized","message":"chave invalida"}}'); return
        if m == "500": self.send_response(500); self.end_headers(); self.wfile.write(b'{"error":{"code":"INTERNAL_ERROR","message":"erro interno"}}'); return
        if m == "slow": time.sleep(11)
        if m == "badjson": self.send_response(200); self.end_headers(); self.wfile.write(b"<html>oops</html>"); return
        if m == "429": self.send_response(429); self.end_headers(); self.wfile.write(b'{"error":{"code":"rate_limited","message":"muitas requisicoes"}}'); return
        path = self.path.replace("/v1", "", 1)
        if path.startswith("/predictions/"): self.send_response(404); self.end_headers(); return
        if path.startswith("/status"): self.send_response(404); self.end_headers(); return
        if path.startswith("/prediction-log/accuracy"): path = "/prediction-log/accuracy"
        if path.startswith("/alerts"): path = "/alerts"
        if path.startswith("/model/metrics"): path = "/model/metrics"
        if path.startswith("/source-health"): path = "/source-health"
        d = mutate(path, m)
        if d is None: self.send_response(404); self.end_headers(); return
        b = json.dumps(d).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 3999), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def text(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", h, flags=re.S); return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
modes = ["ok", "401", "500", "429", "slow", "badjson", "c1_keep", "c1_promote", "prob_invalid", "xss", "empty", "nulls", "big", "missing_field"]
out = {}
DASH = sys.argv[1]
for m in modes:
    MODE["m"] = "401" if m == "401" else m
    import shutil; shutil.rmtree(os.path.join(sys.argv[1], ".next", "cache", "fetch-cache"), ignore_errors=True)
    env = dict(os.environ, PREDITOR_API_BASE_URL="http://127.0.0.1:3999/v1", PREDITOR_API_KEY=("wrong-key" if m == "401" else KEY))
    p = subprocess.Popen(["npx", "next", "start", "-p", "3202"], cwd=DASH, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
    time.sleep(4.5); res = {}
    try:
        for pg in ("/", "/alertas", "/modelo", "/fontes"):
            t0 = time.time()
            try:
                r = urllib.request.urlopen("http://127.0.0.1:3202" + pg, timeout=40); body = r.read().decode(); code = r.status
            except Exception as e:
                body = getattr(e, "read", lambda: b"")().decode() if hasattr(e, "read") else ""; code = getattr(e, "code", "ERR")
            tx = text(body)
            res[pg] = {"http": code, "s": round(time.time() - t0, 1), "simulados": "Dados simulados" in tx, "modo_exemplo": "modo de exemplo" in tx.lower(),
                       "nao_decidido": "Modelo não decidido" in tx, "lixo": [w for w in ("undefined", "NaN", "[object", "Infinity", "null") if w in tx],
                       "script_injetado": "<script>alert" in body or "onerror=alert" in body.replace("&lt;", "<").split("<img")[0] if False else ("<script>alert(2)" in body or "<img src=x onerror" in body),
                       "motivo": (re.search(r"Dados simulados[^.]{0,120}", tx).group(0)[:140] if re.search(r"Dados simulados", tx) else None),
                       "selo": (re.search(r"Modelo em produção ([^·]{0,40}·?[^e]{0,30})", tx).group(1)[:50] if re.search(r"Modelo em produção", tx) else None),
                       "linhas": len(re.findall(r"Livelo →|Prog\d+ →", tx))}
    finally:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM); time.sleep(1)
    out[m] = res; print(m, json.dumps(res, ensure_ascii=False)[:700], flush=True)
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
