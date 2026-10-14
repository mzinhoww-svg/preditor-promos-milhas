import { describe, expect, it } from "vitest";
import predictions from "@/mock/predictions.json";
import modelMetrics from "@/mock/model-metrics.json";
import sourceHealth from "@/mock/source-health.json";
import accuracy from "@/mock/prediction-log-accuracy.json";
import alerts from "@/mock/alerts.json";
import status from "@/mock/status.json";
import explanations from "@/mock/explanations.json";
import {
  InvalidResponseError,
  isIsoDate,
  validateAccuracy,
  validateExplanation,
  validateModelMetrics,
  validatePredictions,
  validateSourceHealth,
  validateStatus,
  validateThresholdAlerts,
} from "../validate";

/** Resposta real de GET /v1/model/metrics da API (T10a) sem walk-forward registrado. */
const REAL_METRICS = {
  generated_at: "2026-10-14T06:29:24Z",
  champion: {
    name: "B1", version: "1.0.0", trained_at: "2026-10-14T06:29:20Z", horizons: [7, 15, 30],
    validation: { method: "walk-forward", folds: 0, period: { from: null, to: null }, by_horizon: {} },
    production: null,
  },
  challenger: null,
  comparison: { horizon: 30, delta_brier: 0.0, delta_log_loss: 0.0, ci_delta_brier: [0.0, 0.0], decision: "keep_champion", note: "sem dados suficientes" },
  reliability: { horizon: 30, bins: [] },
};

/** Item real de GET /v1/predictions: sem IC, sem last_offer, sem reasons. */
const REAL_ITEM = {
  rank: 1, pair: { origin: "Livelo", destination: "Smiles" }, type: "transfer_bonus", segmented: false, segment_label: null,
  windows: { "7": { probability: 0.19781, ci_low: 0.19781, ci_high: 0.19781 }, "15": { probability: 0.37644, ci_low: 0.37644, ci_high: 0.37644 }, "30": { probability: 0.61118, ci_low: 0.61118, ci_high: 0.61118 } },
  bonus_pct: { p25: 70.0, p50: 80.0, p75: 100.0 }, last_offer: null, reasons: [],
};

describe("isIsoDate (N1/F1)", () => {
  it("aceita data e instante válidos", () => {
    expect(isIsoDate("2026-02-28")).toBe(true);
    expect(isIsoDate("2024-02-29")).toBe(true);
    expect(isIsoDate("2026-10-13T06:00:00Z")).toBe(true);
    expect(isIsoDate("2026-10-13T06:00:00.123-03:00")).toBe(true);
  });
  it("rejeita dia inexistente e hora fora da faixa", () => {
    expect(isIsoDate("2026-02-31")).toBe(false);
    expect(isIsoDate("2026-04-31T10:00:00Z")).toBe(false);
    expect(isIsoDate("2026-04-30T24:00:00Z")).toBe(false);
    expect(isIsoDate("2026-13-01")).toBe(false);
    expect(isIsoDate("ontem")).toBe(false);
  });
});

describe("validatePredictions", () => {
  it("aceita o mock inteiro", () => {
    const r = validatePredictions(predictions);
    expect(r.discarded).toBe(0);
    expect(r.data.items.length).toBeGreaterThan(0);
  });
  it("aceita o formato real da API (sem IC, sem last_offer, reasons vazio) e normaliza campos novos", () => {
    const r = validatePredictions({ generated_at: "2026-10-14T00:00:00Z", model: { run_id: "mr_3", name: "B1", version: "1.0.0", role: "champion" }, items: [REAL_ITEM] });
    expect(r.discarded).toBe(0);
    expect(r.data.items[0].method).toBeNull();
    expect(r.data.items[0].n_campaigns).toBeNull();
    expect(r.data.items[0].reasons).toEqual([]);
  });
  it("aceita bonus_pct nulo e method/n_campaigns quando a API passar a mandar", () => {
    const r = validatePredictions({ generated_at: "2026-10-14T00:00:00Z", model: { run_id: "mr_3", name: "B1" }, items: [{ ...REAL_ITEM, bonus_pct: { p25: null, p50: null, p75: null }, method: "B0", n_campaigns: 23 }] });
    expect(r.data.items[0].bonus_pct).toEqual({ p25: null, p50: null, p75: null });
    expect(r.data.items[0].method).toBe("b0");
    expect(r.data.items[0].n_campaigns).toBe(23);
    expect(r.data.model.version).toBeNull();
  });
  it("descarta item com data inválida; janelas faltando ficam nulas e contadas (ressalva 4)", () => {
    const bad1 = { ...REAL_ITEM, last_offer: { start_at: "2026-02-31", end_at: null, bonus_pct: 80, days_since: 3 } };
    const partial = { ...REAL_ITEM, windows: { "7": REAL_ITEM.windows["7"] } };
    const r = validatePredictions({ generated_at: "2026-10-14T00:00:00Z", model: { run_id: "mr_3", name: "B1" }, items: [REAL_ITEM, bad1, partial] });
    expect(r.discarded).toBe(1);
    expect(r.invalidWindows).toBe(2);
    expect(r.data.items).toHaveLength(2);
    expect(r.data.items[1].windows["15"]).toBeNull();
  });
  it("ressalva 4: item com uma janela inválida fica na lista com a janela nula e contada", () => {
    const oneBad = { ...REAL_ITEM, windows: { ...REAL_ITEM.windows, "15": { probability: 1.7, ci_low: 0, ci_high: 1 } } };
    const r = validatePredictions({ generated_at: "2026-10-14T00:00:00Z", model: { run_id: "mr_3", name: "B1" }, items: [oneBad] });
    expect(r.discarded).toBe(0);
    expect(r.invalidWindows).toBe(1);
    expect(r.data.items[0].windows["15"]).toBeNull();
    expect(r.data.items[0].windows["30"]?.probability).toBe(0.61118);
  });
  it("ressalva 4: item com as três janelas inválidas é descartado", () => {
    const allBad = { ...REAL_ITEM, windows: { "7": null, "15": "x", "30": { probability: -1 } } };
    const r = validatePredictions({ generated_at: "2026-10-14T00:00:00Z", model: { run_id: "mr_3", name: "B1" }, items: [allBad] });
    expect(r.discarded).toBe(1);
    expect(r.invalidWindows).toBe(0);
  });
  it("T10b mesclada: model com role 'daily' e champion null (sem decisão) ou referência", () => {
    const base = { generated_at: "2026-10-14T00:00:00Z", items: [REAL_ITEM] };
    const undecided = validatePredictions({ ...base, model: { run_id: "mr_1", name: "B1", version: "1.0.0", role: "daily" }, champion: null });
    expect(undecided.data.model.role).toBe("daily");
    expect(undecided.data.champion).toBeNull();
    const decided = validatePredictions({ ...base, model: { run_id: "mr_1", name: "B1" }, champion: { run_id: "mr_3", name: "B1", version: "1.0.0", role: "champion", trained_at: "2026-10-14T06:29:20Z" } });
    expect(decided.data.champion?.run_id).toBe("mr_3");
  });
  it("rejeita resposta sem items", () => {
    expect(() => validatePredictions({ generated_at: "2026-10-14T00:00:00Z", model: {} })).toThrow(InvalidResponseError);
  });
});

describe("validateModelMetrics", () => {
  it("aceita o mock", () => {
    const m = validateModelMetrics(modelMetrics);
    expect(m.champion?.validation.folds).toBe(18);
    expect(m.reliability.bins.length).toBeGreaterThan(0);
  });
  it("aceita a resposta real sem validação registrada", () => {
    const m = validateModelMetrics(REAL_METRICS);
    expect(m.champion?.validation.folds).toBeNull();
    expect(m.champion?.validation.period).toEqual({ from: null, to: null });
    expect(m.champion?.validation.by_horizon).toEqual({});
    expect(m.champion?.production).toBeNull();
    expect(m.challenger).toBeNull();
    expect(m.comparison.decision).toBe("keep_champion");
    expect(m.reliability.bins).toEqual([]);
  });
  it("ressalva 1: comparação zerada com nota 'sem dados suficientes' não tem dados", () => {
    expect(validateModelMetrics(REAL_METRICS).comparison.has_data).toBe(false);
    expect(validateModelMetrics(modelMetrics).comparison.has_data).toBe(true);
    const zeroNoNote = validateModelMetrics({ ...REAL_METRICS, comparison: { ...REAL_METRICS.comparison, note: "" } });
    expect(zeroNoNote.comparison.has_data).toBe(false);
    const insufficient = validateModelMetrics({ ...REAL_METRICS, comparison: { horizon: 30, delta_brier: -0.01, delta_log_loss: 0.02, ci_delta_brier: [-0.03, 0.01], decision: "insufficient_data", note: "" } });
    expect(insufficient.comparison.has_data).toBe(false);
  });
  it("T10b mesclada: champion null e serving presente; IC degenerado não é dado; is_calibrated só com bins", () => {
    const m = validateModelMetrics({ ...REAL_METRICS, champion: null, serving: { run_id: "mr_1", name: "B1", version: "1.0.0", role: "daily", trained_at: "2026-10-14T06:29:05Z" } });
    expect(m.champion).toBeNull();
    expect(m.serving?.role).toBe("daily");
    expect(m.comparison.has_data).toBe(false);
    expect(m.reliability.is_calibrated).toBe(false);
    const degenerate = validateModelMetrics({ ...REAL_METRICS, champion: { ...REAL_METRICS.champion, validation: { method: "walk-forward", folds: 5, period: { from: "2024-01-01", to: "2026-09-30" }, by_horizon: { "30": { brier: 0.1, log_loss: 0.3, auc: 0.7 } } } }, comparison: { horizon: 30, delta_brier: -0.01, delta_log_loss: 0.01, ci_delta_brier: [0.02, 0.02], decision: "keep_champion", note: "" } });
    expect(degenerate.comparison.has_data).toBe(false);
    const flagged = validateModelMetrics({ ...modelMetrics, reliability: { ...(modelMetrics as { reliability: object }).reliability, is_calibrated: true } });
    expect(flagged.reliability.is_calibrated).toBe(true);
    expect(() => validateModelMetrics({ ...REAL_METRICS, champion: null })).toThrow(InvalidResponseError);
  });
  it("decisão desconhecida vira keep_champion e IC malformado vira null", () => {
    const m = validateModelMetrics({ ...REAL_METRICS, comparison: { ...REAL_METRICS.comparison, decision: "x", ci_delta_brier: [1] } });
    expect(m.comparison.decision).toBe("keep_champion");
    expect(m.comparison.ci_delta_brier).toBeNull();
  });
});

describe("validateSourceHealth", () => {
  it("aceita o mock e a fonte real com contadores nulos", () => {
    expect(validateSourceHealth(sourceHealth).discarded).toBe(0);
    const r = validateSourceHealth({
      generated_at: "2026-10-14T06:29:24Z",
      sources: [{ source: "pontospravoar.com", kind: "rss", status: "error", last_success_at: null, last_item_at: null, items_new_24h: null, items_new_7d: null, extraction_rate_7d: null, error_rate_24h: 1.0, robots_hash: null, robots_changed: true, message: "4 falha(s) consecutiva(s)" }],
    });
    expect(r.discarded).toBe(0);
    expect(r.data.sources[0].items_new_24h).toBeNull();
    expect(r.data.sources[0].extraction_rate_7d).toBeNull();
  });
  it("descarta fonte com status desconhecido", () => {
    const r = validateSourceHealth({ generated_at: "2026-10-14T06:29:24Z", sources: [{ source: "x", kind: "rss", status: "meh", robots_changed: false }] });
    expect(r.discarded).toBe(1);
  });
});

describe("validateAccuracy", () => {
  it("aceita o mock e conta semanas descartadas (F3)", () => {
    const r = validateAccuracy({ ...(accuracy as Record<string, unknown>), weekly: [...(accuracy as { weekly: unknown[] }).weekly, { week: "2026-02-30", horizon: 30, n: 1, hit_rate: 0.5, brier: 0.1 }, { week: "2026-03-02" }] });
    expect(r.discardedWeekly).toBe(2);
  });
  it("aceita a resposta real: period.from nulo, janelas faltando viram n = 0", () => {
    const r = validateAccuracy({ generated_at: "2026-10-14T06:29:24Z", period: { from: null, to: "2026-10-14" }, by_horizon: { "30": { n: 9, hit_rate: 0.33, brier: 0.31, log_loss: 0.85 } }, weekly: [], alerts: [] });
    expect(r.data.period.from).toBeNull();
    expect(r.data.by_horizon["7"].n).toBe(0);
    expect(r.data.by_horizon["30"].n).toBe(9);
  });
});

describe("endpoints da T10b e proposta /v1/status", () => {
  it("valida alertas de limiar e descarta registro malformado", () => {
    const r = validateThresholdAlerts(alerts);
    expect(r.discarded).toBe(0);
    const bad = validateThresholdAlerts({ generated_at: "2026-10-14T00:00:00Z", items: [{ made_at: "2026-10-14T00:00:00Z", pair: { origin: "A", destination: "B" }, type: "transfer_bonus", horizon_days: 30, probability: 1.5, threshold: 0.5 }] });
    expect(bad.discarded).toBe(1);
  });
  it("valida a explicação real e tolera fatores ausentes", () => {
    const e = validateExplanation({ pair: { origin: "Livelo", destination: "Smiles" }, type: "transfer_bonus", as_of: "2026-10-14", windows: { "7": 0.19781, "15": 0.37644, "30": 0.61118 }, factors: { method: "b0", probability_driven_by: "base_rate", n_campaigns: 23, last_campaign_start: "2026-08-03", days_since_last: 72, median_interval_days: 27.0, min_campaigns_b1: 25 } });
    expect(e.factors.method).toBe("b0");
    expect(e.factors.n_campaigns).toBe(23);
    const partial = validateExplanation({ pair: { origin: "A", destination: "B" }, type: "transfer_bonus" });
    expect(partial.factors.method).toBeNull();
    expect(partial.windows).toEqual({});
    for (const raw of Object.values(explanations as Record<string, unknown>)) expect(() => validateExplanation(raw)).not.toThrow();
  });
  it("valida /v1/status e rejeita sem stop.active", () => {
    const s = validateStatus(status);
    expect(s.stop.active).toBe(false);
    expect(s.n_campaigns_total).toBe(312);
    expect(() => validateStatus({ generated_at: "2026-10-14T00:00:00Z", stop: {} })).toThrow(InvalidResponseError);
  });
});
