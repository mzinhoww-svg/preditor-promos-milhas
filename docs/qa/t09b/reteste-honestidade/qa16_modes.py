import http.server, json, subprocess, sys, threading, time, os, re, html, urllib.request, copy, signal, datetime as dt, collections
REAL = "http://127.0.0.1:8055/v1"; KEY = "design-key"
def real(path): return json.loads(urllib.request.urlopen(urllib.request.Request(REAL + path, headers={"X-API-Key": KEY}), timeout=10).read())
BASE = {"/predictions": real("/predictions?limit=50"), "/model/metrics": real("/model/metrics"), "/source-health": real("/source-health"), "/prediction-log/accuracy": real("/prediction-log/accuracy"), "/alerts": real("/alerts")}
EXPL = {}
for it in BASE["/predictions"]["items"]:
    o, d = it["pair"]["origin"], it["pair"]["destination"]
    try: EXPL[(o, d)] = real(f"/predictions/{urllib.request.quote(o)}/{urllib.request.quote(d)}/explanation?type=transfer_bonus")
    except Exception as e: pass
MODE = {"m": "ok"}; HITS = collections.Counter()
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
def mutate(p, m):
    d = copy.deepcopy(BASE.get(p))
    if d is None: return None
    now = dt.datetime.now(dt.UTC)
    if p == "/predictions":
        d["generated_at"] = iso(now - dt.timedelta(minutes=20))
        if m in ("decided_promote", "decided_keep"):
            ch = {"run_id": "mr_9", "name": "B1", "version": "1.0.0", "role": "champion", "trained_at": iso(now)}
            d["champion"] = ch
        if m == "champion_null_explicit": d["champion"] = None
    if p == "/model/metrics":
        c = d["comparison"]
        if m == "metrics_champion_null": d["champion"] = None
        if m == "decided_promote":
            c.update(delta_brier=-0.021, delta_log_loss=-0.04, ci_delta_brier=[-0.04, -0.005], decision="promote_challenger", note="C1 vence B1"); d["champion"]["validation"]["folds"] = 6
        if m == "decided_keep":
            c.update(delta_brier=0.004, delta_log_loss=0.01, ci_delta_brier=[-0.01, 0.02], decision="keep_champion", note="IC inclui zero"); d["champion"]["validation"]["folds"] = 6
        if m == "calibrated":
            d["reliability"] = {"horizon": 30, "is_calibrated": True, "bins": [{"p_mean": 0.1, "observed": 0.12, "n": 20}, {"p_mean": 0.5, "observed": 0.48, "n": 30}]}
        if m == "reliab_bins_not_calibrated":
            d["reliability"] = {"horizon": 30, "is_calibrated": False, "bins": [{"p_mean": 0.1, "observed": 0.3, "n": 20}]}
    if p == "/prediction-log/accuracy":
        if m == "n_small": 
            for h in d["by_horizon"]: d["by_horizon"][h]["n"] = 12
        if m == "n_big":
            for h in d["by_horizon"]: d["by_horizon"][h]["n"] = 120
    return d
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        path = self.path.replace("/v1", "", 1).split("?")[0]; HITS[path.split("/")[1] if "/" in path[1:] else path] += 1
        m = MODE["m"]
        if path.startswith("/status"): self.send_response(404); self.end_headers(); return
        if path.startswith("/predictions/"):
            if m == "expl_429": self.send_response(429); self.end_headers(); self.wfile.write(b'{"error":{"code":"rate_limited","message":"x"}}'); return
            if m == "expl_404": self.send_response(404); self.end_headers(); return
            parts = path.split("/"); key = (urllib.request.unquote(parts[2]), urllib.request.unquote(parts[3])); e = EXPL.get(key)
            if e is None: self.send_response(404); self.end_headers(); return
            b = json.dumps(e).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b); return
        d = mutate(path, m)
        if d is None: self.send_response(404); self.end_headers(); return
        b = json.dumps(d).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 3999), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def text(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", h, flags=re.S); return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
def get(pg):
    try: r = urllib.request.urlopen("http://127.0.0.1:3202" + pg, timeout=40); return r.status, r.read().decode()
    except Exception as e: return getattr(e, "code", "ERR"), ""
DASH = sys.argv[1]; out = {}
def start():
    subprocess.run(["rm", "-rf", os.path.join(DASH, ".next", "cache")])
    env = dict(os.environ, PREDITOR_API_BASE_URL="http://127.0.0.1:3999/v1", PREDITOR_API_KEY=KEY)
    p = subprocess.Popen(["npx", "next", "start", "-p", "3202"], cwd=DASH, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid); time.sleep(4.5); return p
def stop(p): os.killpg(os.getpgid(p.pid), signal.SIGTERM); time.sleep(1)
def grab(rx, tx, n=160):
    m = re.search(rx, tx); return m.group(0)[:n] if m else None
FORBID = [r"probabilidade(s)? calibrada", r"b[ôo]nus previsto", r"faixa prevista", r"fatores que o colocaram ali", r"quartis do b[ôo]nus previsto"]
for m in ["ok", "champion_null_explicit", "metrics_champion_null", "decided_promote", "decided_keep", "calibrated", "reliab_bins_not_calibrated", "n_small", "n_big", "expl_429", "expl_404"]:
    MODE["m"] = m; HITS.clear(); p = start()
    try:
        tx = {}; codes = {}
        for pg in ("/", "/modelo", "/alertas", "/fontes"):
            c, h = get(pg); codes[pg] = c; tx[pg] = text(h)
        allt = " ".join(tx.values())
        out[m] = {"http": codes, "hits_api": dict(HITS), "cabecalho": grab(r"Modelo em produção .{0,90}", tx["/"], 110),
                  "kpi_prob": grab(r"[Pp]robabilidade[s]? (estimada|calibrada)[^.]{0,40}", tx["/"], 70),
                  "bonus_rotulo": grab(r"Bônus nas campanhas anteriores[^.]{0,40}|mediana histórica[^.]{0,30}", tx["/"], 90),
                  "dados_de": grab(r"dados de \d\d:\d\d UTC", tx["/"]) or grab(r"dados de [^ ]+ UTC", allt),
                  "modelo_decisao": grab(r"(Modelo não decidido|Campeão|Servindo \(sem decisão\))[^.]{0,120}", tx["/modelo"], 170),
                  "cmp": grab(r"Não decidido:[^.]{0,200}|Campeão mantido[^.]{0,80}|Promover desafiante[^.]{0,80}", tx["/modelo"], 220),
                  "delta_visivel": bool(re.search(r"Δ Brier \(desafiante[^)]*\)\s*[−+-]?\d,\d+", tx["/modelo"])) or bool(re.search(r"IC do Δ Brier [−+-]?\d,\d+ a", tx["/modelo"])),
                  "amostra": grab(r"amostra pequena[^.]{0,40}|Amostra pequena[^.]{0,60}", tx["/modelo"], 100),
                  "proibidos": [rx for rx in FORBID if re.search(rx, allt, re.I)],
                  "lixo": [w for w in ("undefined", "NaN", "[object") if w in allt]}
    finally: stop(p)
    print(m, json.dumps(out[m], ensure_ascii=False), flush=True)
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
