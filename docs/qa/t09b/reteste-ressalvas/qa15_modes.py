import http.server, json, subprocess, sys, threading, time, os, re, html, urllib.request, copy, signal, datetime as dt
REAL = "http://127.0.0.1:8055/v1"; KEY = "design-key"
def real(path): return json.loads(urllib.request.urlopen(urllib.request.Request(REAL + path, headers={"X-API-Key": KEY}), timeout=10).read())
BASE = {"/predictions": real("/predictions?limit=50"), "/model/metrics": real("/model/metrics"), "/source-health": real("/source-health"), "/prediction-log/accuracy": real("/prediction-log/accuracy"), "/alerts": real("/alerts")}
MODE = {"m": "ok"}
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
def mutate(p, m):
    d = copy.deepcopy(BASE.get(p))
    if d is None: return None
    now = dt.datetime.now(dt.UTC)
    if p == "/predictions":
        d["generated_at"] = iso(now - dt.timedelta(hours=3)) if m == "fresh3h" else (iso(now - dt.timedelta(days=3)) if m == "stale" else iso(now))
        if m == "invalid_window":
            d["items"][0]["windows"]["15"]["probability"] = 1.8
        if m == "all_invalid":
            for h in ("7", "15", "30"): d["items"][0]["windows"][h]["probability"] = "x"
        if m == "mixed_methods":
            d["items"][0]["method"] = "b0"; d["items"][1]["method"] = "b1"; d["items"][2]["method"] = "b1"
        if m == "only_b0":
            for it in d["items"]: it["method"] = "b0"
        if m == "c1":
            d["model"]["name"] = "C1"; d["model"]["champion"]["name"] = "C1"
        if m == "name_b0": d["model"]["name"] = "B0"; d["model"]["champion"]["name"] = "B0"
    if p == "/model/metrics":
        c = d["comparison"]
        if m == "cmp_real":
            c.update(delta_brier=-0.021, delta_log_loss=-0.04, ci_delta_brier=[-0.04, -0.005], decision="promote_challenger", note="C1 vence B1")
            d["champion"]["validation"]["folds"] = 6
        if m == "cmp_delta0_ci": 
            c.update(delta_brier=0.0, delta_log_loss=0.001, ci_delta_brier=[-0.01, 0.01], decision="keep_champion", note="")
            d["champion"]["validation"]["folds"] = 6
        if m == "cmp_insufficient": c.update(decision="insufficient_data", note="", delta_brier=0.012, ci_delta_brier=[-0.02, 0.03])
        if m == "cmp_null": d["comparison"] = None
    return d
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if MODE["m"] == "500": self.send_response(500); self.end_headers(); self.wfile.write(b"{}"); return
        path = self.path.replace("/v1", "", 1).split("?")[0]
        if path.startswith("/predictions/") or path.startswith("/status"): self.send_response(404); self.end_headers(); return
        d = mutate(path, MODE["m"])
        if d is None: self.send_response(404); self.end_headers(); return
        b = json.dumps(d).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 3999), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def text(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", h, flags=re.S); return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
def get(pg):
    try: r = urllib.request.urlopen("http://127.0.0.1:3202" + pg, timeout=40); return r.status, r.read().decode()
    except Exception as e: return getattr(e, "code", "ERR"), ""
DASH = sys.argv[1]; out = {}
def start(key=KEY):
    shutil_rm = os.path.join(DASH, ".next", "cache"); subprocess.run(["rm", "-rf", shutil_rm])
    env = dict(os.environ, PREDITOR_API_BASE_URL="http://127.0.0.1:3999/v1", PREDITOR_API_KEY=key)
    p = subprocess.Popen(["npx", "next", "start", "-p", "3202"], cwd=DASH, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid); time.sleep(4.5); return p
def stop(p): os.killpg(os.getpgid(p.pid), signal.SIGTERM); time.sleep(1)
def grab(rx, tx, n=140):
    m = re.search(rx, tx); return m.group(0)[:n] if m else None
for m in ["ok", "fresh3h", "stale", "invalid_window", "all_invalid", "mixed_methods", "only_b0", "name_b0", "c1", "cmp_real", "cmp_delta0_ci", "cmp_insufficient", "cmp_null"]:
    MODE["m"] = m; p = start()
    try:
        c, h = get("/"); t = text(h); c2, h2 = get("/modelo"); t2 = text(h2)
        out[m] = {"home_http": c, "cabecalho_modelo": grab(r"Modelo em produção .{0,60}", t, 90), "frescor": grab(r"API consultada.{0,120}", t, 170), "dado_velho": "dado velho" in t,
                  "janela_invalida": t.count("janela inválida"), "linhas": len(re.findall(r"Livelo →|Esfera →", t)), "descartados": grab(r"\d+ itens? da API foi?[^.]{0,60}|\d+ itens da API foram[^.]{0,60}", t),
                  "modelo_http": c2, "comparacao": grab(r"Campeão (mantido|substituído|em avaliação)[^A-Z]{0,90}|Sem dados[^.]{0,100}", t2, 160), "delta_visivel": bool(re.search(r"Δ Brier [−+-]?0,\d+", t2)),
                  "lixo": [w for w in ("undefined", "NaN", "[object") if w in t + t2]}
    finally: stop(p)
    print(m, json.dumps(out[m], ensure_ascii=False), flush=True)
# ---- cache: API boa -> cai -> proxima requisicao na mesma instancia
MODE["m"] = "ok"; p = start()
try:
    c, h = get("/"); a = "Dados simulados" in text(h)
    MODE["m"] = "500"; c, h = get("/"); b = "Dados simulados" in text(h)
    out["sem_cache"] = {"antes_da_queda_simulados": a, "logo_apos_queda_simulados": b}
finally: stop(p)
print("sem_cache", out["sem_cache"])
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
