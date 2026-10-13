import http from "node:http"; import fs from "node:fs";
const M = process.argv[2]; const scenario = process.argv[3]; const port = +process.argv[4];
const rd = (f) => JSON.parse(fs.readFileSync(`${M}/${f}.json`, "utf8"));
const pred = rd("predictions"), met = rd("model-metrics"), src = rd("source-health"), acc = rd("prediction-log-accuracy");
const base = pred.items[0];
const mk = (over, i) => structuredClone({ ...base, rank: i + 1, ...over });
let P = structuredClone(pred), MET = met, SRC = src, ACC = acc;
if (scenario === "empty") { P.items = []; SRC.sources = []; ACC.alerts = []; }
if (scenario === "extremes") {
  const z = { "7": { probability: 0, ci_low: 0, ci_high: 0 }, "15": { probability: 1, ci_low: 1, ci_high: 1 }, "30": { probability: 1, ci_low: 0.99, ci_high: 1 } };
  const long = "Programa de Fidelidade com Nome Absurdamente Longo e Sem Espacos_" + "X".repeat(180);
  P.items = [
    mk({ windows: z, pair: { origin: long, destination: "Smiles" } }, 0),
    mk({ pair: { origin: "Livelo", destination: long }, segmented: true, segment_label: "Clube Livelo Diamante " + "Y".repeat(120), reasons: [{ kind: "other", label: "Fator " + "z".repeat(300), detail: "d ".repeat(200), weight: 1 }] }, 1),
    mk({ last_offer: null, reasons: [], windows: { "7": { probability: 0.5, ci_low: 0.5, ci_high: 0.5 }, "15": { probability: 0.0004, ci_low: 0, ci_high: 0.001 }, "30": { probability: 0.9996, ci_low: 0.99, ci_high: 1 } } }, 2),
    mk({ pair: { origin: "Esfera", destination: "Esfera" }, bonus_pct: { p25: 0, p50: 0, p75: 0 } }, 3),
  ];
  P.items.push(structuredClone(P.items[3])); // duplicata exata (mesma key)
  MET = structuredClone(met); MET.challenger = null; MET.champion.production = null;
  SRC = structuredClone(src); SRC.sources[0].last_success_at = null; SRC.sources[0].last_item_at = null; SRC.sources[0].message = "M".repeat(400);
}
if (scenario === "missing") { // campos opcionais/obrigatorios ausentes
  P.items = [mk({}, 0)]; delete P.items[0].windows["15"]; // janela ausente
  P.items.push(mk({}, 1)); delete P.items[1].bonus_pct;
}
if (scenario === "badjson") { P = { generated_at: "nao-e-data", model: {}, items: "x" }; }

if (scenario === "baddate") { P.generated_at = "lixo"; MET = structuredClone(met); MET.generated_at = "lixo"; SRC = structuredClone(src); SRC.generated_at = "lixo"; SRC.sources[0].last_success_at = "ontem"; ACC = structuredClone(acc); ACC.generated_at = "lixo"; ACC.alerts[0] && (ACC.alerts[0].since = "x"); }
if (scenario === "nociband") { MET = structuredClone(met); delete MET.champion.validation.by_horizon["7"].ci_brier; delete MET.comparison.ci_delta_brier; MET.reliability.bins = []; MET.champion.validation.folds = undefined; }
if (scenario === "oddnums") { P.items = [mk({ windows: { "7": { probability: 1.2, ci_low: 0, ci_high: 1 }, "15": { probability: 0.5, ci_low: 0.6, ci_high: 0.4 }, "30": { probability: 0.5, ci_low: 0.5, ci_high: 0.5 } } }, 0), mk({ bonus_pct: { p25: 90, p50: 50, p75: 10 }, last_offer: { start_at: "2026-09-12", end_at: "2026-09-01", bonus_pct: -5, days_since: -3 } }, 1), mk({ rank: 1e12 }, 2), mk({ last_offer: { start_at: "nao-data", end_at: null, bonus_pct: 80, days_since: 3 } }, 3), mk({ type: "boosted_accrual", pair: { origin: "", destination: "" } }, 4)]; }
if (scenario === "oddnums2") { P.items = [mk({ windows: { "7": { probability: 1, ci_low: 0, ci_high: 1 }, "15": { probability: 0.5, ci_low: 0.6, ci_high: 0.4 }, "30": { probability: 0.5, ci_low: 0.5, ci_high: 0.5 } } }, 0), mk({ bonus_pct: { p25: 90, p50: 50, p75: 10 }, last_offer: { start_at: "2026-09-12", end_at: "2026-09-01", bonus_pct: -5, days_since: -3 } }, 1), mk({ rank: 1e12 }, 2), mk({ type: "boosted_accrual", pair: { origin: "", destination: "" } }, 3)]; }
if (scenario === "calinvalid") { P.items = [mk({ last_offer: { start_at: "2026-02-31", end_at: "2026-03-05", bonus_pct: 80, days_since: 12 } }, 0), mk({}, 1)]; ACC = structuredClone(acc); ACC.alerts = [{ ...acc.alerts[0], id: "x1", since: "2026-02-30T10:00:00Z", title: "Alerta com data impossivel" }, ...acc.alerts.slice(1)]; }
if (scenario === "mixed") { P.items = [mk({}, 0), mk({ last_offer: { start_at: "nao-data", end_at: null, bonus_pct: 80, days_since: 3 } }, 1), mk({}, 2)]; SRC = structuredClone(src); SRC.sources[0].last_success_at = "ontem"; ACC = structuredClone(acc); ACC.alerts = [{ ...acc.alerts[0], id: "bad", since: "lixo" }, ...acc.alerts.slice(1)]; ACC.weekly = [{ week: "2026-W41", horizon: 7, n: 3, hit_rate: 0.5, brier: 0.2 }, ...acc.weekly]; }
const routes = { "/v1/predictions": () => P, "/v1/model/metrics": () => MET, "/v1/source-health": () => SRC, "/v1/prediction-log/accuracy": () => ACC };
http.createServer((req, res) => {
  const p = new URL(req.url, "http://x").pathname;
  console.log(new Date().toISOString(), req.method, p, "key:", req.headers["x-api-key"] ? "present" : "ABSENT");
  if (scenario === "error500") { res.writeHead(500, { "content-type": "application/json" }); return res.end(JSON.stringify({ error: { code: "internal", message: "Falha interna SECRET_DETAIL_stacktrace_xyz" } })); }
  if (scenario === "slow") { return setTimeout(() => { res.writeHead(200, {"content-type":"application/json"}); res.end(JSON.stringify(routes[p]?.() ?? {})); }, 60000); }
  const r = routes[p]; if (!r) { res.writeHead(404); return res.end("{}"); }
  res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify(r()));
}).listen(port, "127.0.0.1", () => console.log("fake api", scenario, port));
