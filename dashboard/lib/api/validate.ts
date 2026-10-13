import "server-only";
import type {
  AccuracyResponse,
  Alert,
  Horizon,
  ModelMetricsResponse,
  ModelSummary,
  PredictionItem,
  PredictionsResponse,
  SourceHealth,
  SourceHealthResponse,
  WindowProbability,
} from "./types";

/**
 * D4: a resposta da API é validada antes de chegar às telas. Item de predição
 * inválido é descartado e contado; resposta com formato errado vira erro.
 */
export class InvalidResponseError extends Error {
  constructor(
    public readonly endpoint: string,
    message: string,
  ) {
    super(`${endpoint}: ${message}`);
    this.name = "InvalidResponseError";
  }
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isProb = (v: unknown): v is number => isNum(v) && v >= 0 && v <= 1;
const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-](\d{2}):?(\d{2}))?)?$/;
/**
 * N1/F1: data ISO 8601 (YYYY-MM-DD ou instante) com calendário válido. O Date
 * aceita 2026-02-31 e rola para 03/03; aqui o dia precisa existir no mês e
 * hora, minuto, segundo e fuso precisam estar na faixa.
 */
const isIsoDate = (v: unknown): v is string => {
  if (!isStr(v)) return false;
  const m = ISO_RE.exec(v);
  if (!m) return false;
  const [y, mo, d, hh = "0", mi = "0", ss = "0", tzh = "0", tzm = "0"] = m.slice(1);
  const Y = +y, Mo = +mo, D = +d;
  const utc = new Date(Date.UTC(Y, Mo - 1, D));
  if (utc.getUTCFullYear() !== Y || utc.getUTCMonth() !== Mo - 1 || utc.getUTCDate() !== D) return false;
  return +hh < 24 && +mi < 60 && +ss < 60 && +tzh < 24 && +tzm < 60;
};
const isIsoDateOrNull = (v: unknown): v is string | null | undefined => v === null || v === undefined || isIsoDate(v);
/** N2: par [num, num] opcional; ausente ou malformado vira null. */
const pairOrNull = (v: unknown): [number, number] | null =>
  Array.isArray(v) && v.length === 2 && v.every(isNum) ? [v[0], v[1]] : null;

const OFFER_TYPES = new Set(["transfer_bonus", "purchase_discount", "boosted_accrual"]);
const REASON_KINDS = new Set(["days_since_last", "month", "sibling_pairs", "source_signal", "other"]);
const HORIZON_KEYS: Horizon[] = ["7", "15", "30"];

function isWindow(v: unknown): v is WindowProbability {
  return isObj(v) && isProb(v.probability) && isProb(v.ci_low) && isProb(v.ci_high);
}

export function isPredictionItem(v: unknown): v is PredictionItem {
  if (!isObj(v)) return false;
  if (!isNum(v.rank)) return false;
  if (!isObj(v.pair) || !isStr(v.pair.origin) || !isStr(v.pair.destination)) return false;
  if (!isStr(v.type) || !OFFER_TYPES.has(v.type)) return false;
  if (typeof v.segmented !== "boolean") return false;
  if (!(v.segment_label === null || v.segment_label === undefined || isStr(v.segment_label))) return false;
  const w = v.windows;
  if (!isObj(w) || !HORIZON_KEYS.every((h) => isWindow(w[h]))) return false;
  const b = v.bonus_pct;
  if (!isObj(b) || !isNum(b.p25) || !isNum(b.p50) || !isNum(b.p75)) return false;
  const lo = v.last_offer;
  if (!(lo === null || lo === undefined)) {
    if (!isObj(lo) || !isIsoDate(lo.start_at) || !isNum(lo.bonus_pct) || !isNum(lo.days_since)) return false;
    if (!isIsoDateOrNull(lo.end_at)) return false;
  }
  if (!Array.isArray(v.reasons)) return false;
  for (const r of v.reasons) {
    if (!isObj(r) || !isStr(r.kind) || !REASON_KINDS.has(r.kind) || !isStr(r.label) || !isNum(r.weight)) return false;
    if (!(r.detail === null || r.detail === undefined || isStr(r.detail))) return false;
  }
  return true;
}

export function validatePredictions(raw: unknown): { data: PredictionsResponse; discarded: number } {
  if (!isObj(raw) || !isIsoDate(raw.generated_at) || !isObj(raw.model) || !Array.isArray(raw.items)) {
    throw new InvalidResponseError("/predictions", "formato inesperado");
  }
  const m = raw.model;
  if (!isStr(m.run_id) || !isStr(m.name) || !isStr(m.version)) {
    throw new InvalidResponseError("/predictions", "campo model inválido");
  }
  const items = raw.items.filter(isPredictionItem).map((it) => ({
    ...it,
    segment_label: it.segment_label ?? null,
    last_offer: it.last_offer ? { ...it.last_offer, end_at: it.last_offer.end_at ?? null } : null,
    reasons: it.reasons.map((r) => ({ ...r, detail: r.detail ?? null })),
  }));
  return {
    data: { generated_at: raw.generated_at, model: m as PredictionsResponse["model"], items },
    discarded: raw.items.length - items.length,
  };
}

function hasHorizonMetrics(v: unknown, keys: string[]): boolean {
  return isObj(v) && HORIZON_KEYS.every((h) => isObj(v[h]) && keys.every((k) => isNum((v[h] as Record<string, unknown>)[k])));
}

function isModelSummary(v: unknown): boolean {
  if (!isObj(v) || !isStr(v.name) || !isStr(v.version) || !isIsoDate(v.trained_at)) return false;
  const val = v.validation;
  if (!isObj(val) || !isStr(val.method) || !hasHorizonMetrics(val.by_horizon, ["brier", "log_loss", "auc"])) return false;
  if (!isObj(val.period) || !isIsoDate(val.period.from) || !isIsoDate(val.period.to)) return false;
  const prod = v.production;
  if (prod === null || prod === undefined) return true;
  if (!isObj(prod) || !isObj(prod.period) || !isIsoDate(prod.period.from) || !isIsoDate(prod.period.to)) return false;
  return hasHorizonMetrics(prod.by_horizon, ["brier", "log_loss", "hit_rate", "n"]) && isNum(prod.n_predictions) && isNum(prod.n_resolved);
}

/** F2: folds precisa ser inteiro positivo; qualquer outra coisa vira null. */
const foldsOrNull = (v: unknown): number | null => (Number.isInteger(v) && (v as number) > 0 ? (v as number) : null);

/** Normaliza um ModelSummary já validado: ci_brier ausente vira null (N2); folds inválido vira null (F2). */
function normalizeModelSummary(v: ModelSummary): ModelSummary {
  const by = { ...v.validation.by_horizon };
  for (const h of HORIZON_KEYS) by[h] = { ...by[h], ci_brier: pairOrNull(by[h].ci_brier) };
  return {
    ...v,
    validation: { ...v.validation, folds: foldsOrNull(v.validation.folds), by_horizon: by },
    production: v.production ?? null,
  };
}

export function validateModelMetrics(raw: unknown): ModelMetricsResponse {
  if (!isObj(raw) || !isIsoDate(raw.generated_at) || !isModelSummary(raw.champion)) {
    throw new InvalidResponseError("/model/metrics", "formato inesperado");
  }
  if (!(raw.challenger === null || raw.challenger === undefined || isModelSummary(raw.challenger))) {
    throw new InvalidResponseError("/model/metrics", "challenger inválido");
  }
  const c = raw.comparison;
  if (!isObj(c) || !isNum(c.horizon) || !isNum(c.delta_brier) || !isNum(c.delta_log_loss) || !isStr(c.decision)) {
    throw new InvalidResponseError("/model/metrics", "comparison inválido");
  }
  const r = raw.reliability;
  if (!isObj(r) || !isNum(r.horizon) || !Array.isArray(r.bins)) {
    throw new InvalidResponseError("/model/metrics", "reliability inválido");
  }
  const bins = r.bins.filter((b): b is { p_mean: number; observed: number; n: number } => isObj(b) && isProb(b.p_mean) && isProb(b.observed) && isNum(b.n));
  const out = raw as unknown as ModelMetricsResponse;
  return {
    ...out,
    challenger: out.challenger ? normalizeModelSummary(out.challenger) : null,
    champion: normalizeModelSummary(out.champion),
    comparison: { ...out.comparison, note: isStr(c.note) ? c.note : "", ci_delta_brier: pairOrNull(c.ci_delta_brier) },
    reliability: { horizon: r.horizon, bins },
  };
}

const SOURCE_STATUS = new Set(["ok", "degraded", "stale", "blocked", "error"]);
const SOURCE_KIND = new Set(["rss", "html", "wayback", "official"]);

function isSource(v: unknown): v is SourceHealth {
  return (
    isObj(v) &&
    isStr(v.source) &&
    isStr(v.kind) && SOURCE_KIND.has(v.kind) &&
    isStr(v.status) && SOURCE_STATUS.has(v.status) &&
    isNum(v.items_new_24h) && isNum(v.items_new_7d) && isNum(v.extraction_rate_7d) && isNum(v.error_rate_24h) &&
    typeof v.robots_changed === "boolean"
  );
}

export function validateSourceHealth(raw: unknown): { data: SourceHealthResponse; discarded: number } {
  if (!isObj(raw) || !isIsoDate(raw.generated_at) || !Array.isArray(raw.sources)) {
    throw new InvalidResponseError("/source-health", "formato inesperado");
  }
  const sources = raw.sources.filter(isSource).map((s) => ({
    ...s,
    last_success_at: isIsoDate(s.last_success_at) ? s.last_success_at : null,
    last_item_at: isIsoDate(s.last_item_at) ? s.last_item_at : null,
    robots_hash: isStr(s.robots_hash) ? s.robots_hash : null,
    message: isStr(s.message) ? s.message : null,
  }));
  return { data: { generated_at: raw.generated_at, sources }, discarded: raw.sources.length - sources.length };
}

const SEVERITY = new Set(["info", "warning", "critical"]);
const ALERT_KIND = new Set(["drift", "source", "budget", "pipeline", "model"]);

function isAlert(v: unknown): v is Alert {
  return (
    isObj(v) && isStr(v.id) && isStr(v.severity) && SEVERITY.has(v.severity) && isStr(v.kind) && ALERT_KIND.has(v.kind) && isStr(v.title) && isStr(v.detail) && isIsoDate(v.since)
  );
}

export function validateAccuracy(raw: unknown): { data: AccuracyResponse; discarded: number; discardedWeekly: number } {
  if (
    !isObj(raw) ||
    !isIsoDate(raw.generated_at) ||
    !isObj(raw.period) ||
    !isIsoDate(raw.period.from) ||
    !isIsoDate(raw.period.to) ||
    !hasHorizonMetrics(raw.by_horizon, ["n", "hit_rate", "brier", "log_loss"])
  ) {
    throw new InvalidResponseError("/prediction-log/accuracy", "formato inesperado");
  }
  // F3: semana malformada é descartada e contada, como itens e alertas.
  const rawWeekly = Array.isArray(raw.weekly) ? raw.weekly : [];
  const weekly = rawWeekly.filter(
    (w): w is AccuracyResponse["weekly"][number] => isObj(w) && isIsoDate(w.week) && isNum(w.horizon) && isNum(w.n) && isProb(w.hit_rate) && isNum(w.brier),
  );
  const rawAlerts = Array.isArray(raw.alerts) ? raw.alerts : [];
  const alerts = rawAlerts.filter(isAlert).map((a) => ({
    ...a,
    related: isObj(a.related)
      ? {
          horizon: isNum(a.related.horizon) ? a.related.horizon : null,
          source: isStr(a.related.source) ? a.related.source : null,
          pair: isStr(a.related.pair) ? a.related.pair : null,
        }
      : { horizon: null, source: null, pair: null },
  }));
  const out = raw as unknown as AccuracyResponse;
  return {
    data: { generated_at: out.generated_at, period: out.period, by_horizon: out.by_horizon, weekly, alerts },
    discarded: rawAlerts.length - alerts.length,
    discardedWeekly: rawWeekly.length - weekly.length,
  };
}
