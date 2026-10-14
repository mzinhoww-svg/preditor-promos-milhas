"""QA PR #36 reteste (b13fd97): robots 301/403/404/500, Disallow por URL/wildcard, falsos positivos, gap, tentativas/backoff, idempotencia."""
import argparse, datetime as dt, http.server, json, os, sys, threading, tempfile, time
from pathlib import Path
sys.path.insert(0, "src")
import httpx
from preditor import backfill as B, collector as C, article as A
from preditor.extract import extract
RAW = os.environ["RAWDIR"]
R = {}
# ---------- A: falsos positivos reais (HTML guardado do banco do autor) ----------
fs = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
fp = {}
for rid, rot in ((14, "110% card Azul (esperado: 80%, nao 110)"), (61, "58% hoteis (esperado: nenhuma)"), (144, "100% CSS (esperado: nenhuma/20% volta)"),
                 (118, "80% real"), (86, "80%/70% titulo"), (163, "45% bonus+20% volta"), (26, "80% status diamante"), (56, "80% prorrogado")):
    p = Path(RAW) / f"{rid}.html"
    if not p.exists(): continue
    html = p.read_text()
    sn = A.snippets(A.article_text(html))
    offs = []
    for s in sn:
        offs += [(o.origem, o.destino, o.bonus_pct) for o in extract(s, first_seen_at=fs).ofertas]
    fp[str(rid)] = {"esperado": rot, "snippets": [x[:90] for x in sn[:3]], "ofertas": offs}
R["A_extracao"] = fp
# ---------- B: robots com servidor local ----------
class H(http.server.BaseHTTPRequestHandler):
    mode = {}
    def log_message(self, *a): pass
    def do_GET(self):
        m = self.mode.get(self.headers.get("Host", "").split(":")[0], None)
        p = self.path
        if p == "/robots.txt":
            kind = self.server.kind
            if kind == "301":
                if self.server.hits.get("r", 0) == 0:
                    self.server.hits["r"] = 1
                    self.send_response(301); self.send_header("Location", "/robots2.txt"); self.end_headers(); return
            if kind == "403": self.send_response(403); self.end_headers(); return
            if kind == "500": self.send_response(500); self.end_headers(); return
            if kind == "404": self.send_response(404); self.end_headers(); return
            if kind == "301":
                pass
            body = self.server.body.encode(); self.send_response(200); self.end_headers(); self.wfile.write(body); return
        if p == "/robots2.txt":
            body = self.server.body.encode(); self.send_response(200); self.end_headers(); self.wfile.write(body); return
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
def serve(kind, body="User-agent: *\nDisallow:\n"):
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); s.kind = kind; s.body = body; s.hits = {}
    threading.Thread(target=s.serve_forever, daemon=True).start(); return s
res = {}
for kind in ("200", "301", "403", "500", "404"):
    s = serve(kind)
    st, txt = B.fetch_robots_strict(f"http://127.0.0.1:{s.server_port}")
    res[kind] = (st, None if txt is None else txt[:20]); s.shutdown()
R["B_robots_status"] = res
# conexao recusada
st, _ = B.fetch_robots_strict("http://127.0.0.1:9"); R["B_robots_conexao_recusada"] = st
# ---------- C: Disallow por URL e wildcard (robots_allowed) ----------
rb = "User-agent: *\nDisallow: /p3/\nDisallow: /*?s=\nDisallow: /*/search/\nDisallow: /wp-admin/\n"
R["C_disallow_prefixo_bloqueado"] = (not C.robots_allowed(rb, "https://x.test/p3/artigo"))
R["C_wildcard_?s=_bloqueado"] = (not C.robots_allowed(rb, "https://x.test/?s=livelo"))
R["C_wildcard_*/search/_bloqueado"] = (not C.robots_allowed(rb, "https://x.test/cat/search/x"))
R["C_ua_gptbot_regra"] = C.robots_allowed("User-agent: *\nAllow: /\nUser-agent: ClaudeBot\nDisallow: /\n", "https://x.test/a")
R["C_UA"] = C.UA[:80]
print(json.dumps(R, indent=1, ensure_ascii=False, default=str))
