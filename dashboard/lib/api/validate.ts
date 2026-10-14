import "server-only";
import type {
  AccuracyResponse,
  Alert,
  Explanation,
  Horizon,
  Method,
  ModelMetricsResponse,
  ModelSummary,
  PredictionItem,
  PredictionsResponse,
  ProductionMetrics,
  SourceHealth,
  SourceHealthResponse,
  StatusResponse,
  ThresholdAlert,
  ThresholdAlertsResponse,
  ValidationMetrics,
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
const numOrNull = (v: unknown): number | null => (isNum(v) ? v : null);
const strOrNull = (v: unknown): string | null => (isStr(v) ? v : null);
const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-](\d{2}):?(\d{2}))?)?$/;
/**
 * N1/F1: data ISO 8601 (YYYY-MM-DD ou instante) com calendário válido. O Date
 * aceita 2026-02-31 e rola para 03/03; aqui o dia precisa existir no mês e
 * hora, minuto, segundo e fuso precisam estar na faixa.
 */
export const isIsoDate = (v: unknown): v is string => {
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
const isoOrNull = (v: unknown): string | null => (isIsoDate(v) ? v : null);
/** N2: par [num, num] opcional; ausente ou malformado vira null. */
const pairOrNull = (v: unknown): [number, number] | null =>
  Array.isArray(v) && v.length === 2 && v.every(isNum) ? [v[0], v[1]] : null;
const methodOrNull = (v: unknown): Method | null => (v === "b0" || v === "b1" ? v : isStr(v) && /^b[01]$/i.test(v) ? (v.toLowerCase() as Method) : null);

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
  // bonus_pct: objeto com quartis numéricos ou nulos (par sem histórico de bônus).
  const b = v.bonus_pct;
  if (!isObj(b)) return false;
  for (const k of ["p25", "p50", "p75"]) if (!(b[k] === null || b[k] === undefined || isNum(b[k]))) return false;
  const lo = v.last_offer;
  if (!(lo === null || lo === undefined)) {
    if (!isObj(lo) || !isIsoDate(lo.start_at) || !isNum(lo.bonus_pct) || !isNum(lo.days_since)) return false;
    if (!isIsoDateOrNull(lo.end_at)) return false;
  }
  if (!(v.reasons === undefined || Array.isArray(v.reasons))) return false;
  for (const r of (v.reasons ?? []) as unknown[]) {
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
  if (!isStr(m.run_id) || !isStr(m.name)) {
    throw new InvalidResponseError("/predictions", "campo model inválido");
  }
  const items = raw.items.filter(isPredictionItem).map((it) => {
    const extra = it as unknown as Record<string, unknown>;
    const b = it.bonus_pct as Record<string, unknown>;
    return {
      ...it,
      segment_label: it.segment_label ?? null,
      bonus_pct: { p25: numOrNull(b.p25), p50: numOrNull(b.p50), p75: numOrNull(b.p75) },
      last_offer: it.last_offer ? { ...it.last_offer, end_at: it.last_offer.end_at ?? null } : null,
      reasons: (it.reasons ?? []).map((r) => ({ ...r, detail: r.detail ?? null })),
      method: methodOrNull(extra.method),
      n_campaigns: numOrNull(extra.n_campaigns),
    };
  });
  return {
    data: {
      generated_at: raw.generated_at,
      model: { run_id: m.run_id, name: m.name, version: strOrNull(m.version), role: m.role === "challenger" ? "challenger" : "champion" },
      items,
    },
    discarded: raw.items.length - items.length,
  };
}

function horizonMetrics<T>(v: unknown, keys: (keyof T & string)[]): Partial<Record<Horizon, T>> {
  const out: Partial<Record<Horizon, T>> = {};
  if (!isObj(v)) return out;
  for (const h of HORIZON_KEYS) {
    const m = v[h];
    if (isObj(m) && keys.every((k) => isNum(m[k]))) out[h] = m as unknown as T;
  }
  return out;
}

function periodOrNull(v: unknown): { from: string | null; to: string | null } {
  return isObj(v) ? { from: isoOrNull(v.from), to: isoOrNull(v.to) } : { from: null, to: null };
}

/** F2: folds precisa ser inteiro positivo; qualquer outra coisa vira null. */
const foldsOrNull = (v: unknown): number | null => (Number.isInteger(v) && (v as number) > 0 ? (v as number) : null);

/**
 * ModelSummary tolerante: a API de produção devolve validação vazia
 * (period null, by_horizon {}) enquanto o modelo não tem walk-forward registrado.
 */
function modelSummary(v: unknown): ModelSummary | null {
  if (!isObj(v) || !isStr(v.name) || !isIsoDate(v.trained_at)) return null;
  const val = isObj(v.validation) ? v.validation : {};
  const by = horizonMetrics<ValidationMetrics>(val.by_horizon, ["brier", "log_loss", "auc"]);
  for (const h of HORIZON_KEYS) if (by[h]) by[h] = { ...by[h]!, ci_brier: pairOrNull((by[h] as unknown as Record<string, unknown>).ci_brier) };
  let production: ModelSummary["production"] = null;
  const prod = v.production;
  if (isObj(prod)) {
    production = {
      period: periodOrNull(prod.period),
      n_predictions: isNum(prod.n_predictions) ? prod.n_predictions : 0,
      n_resolved: isNum(prod.n_resolved) ? prod.n_resolved : 0,
      by_horizon: horizonMetrics<ProductionMetrics>(prod.by_horizon, ["brier", "log_loss", "hit_rate", "n"]),
    };
  }
  return {
    name: v.name,
    version: isStr(v.version) ? v.version : "—",
    trained_at: v.trained_at,
    horizons: Array.isArray(v.horizons) ? v.horizons.filter(isNum) : [7, 15, 30],
    validation: {
      method: isStr(val.method) && val.method ? val.method : "walk-forward",
      folds: foldsOrNull(val.folds),
      period: periodOrNull(val.period),
      by_horizon: by,
    },
    production,
  };
}

export function validateModelMetrics(raw: unknown): ModelMetricsResponse {
  if (!isObj(raw) || !isIsoDate(raw.generated_at)) {
    throw new InvalidResponseError("/model/metrics", "formato inesperado");
  }
  const champion = modelSummary(raw.champion);
  if (!champion) throw new InvalidResponseError("/model/metrics", "champion inválido");
  const challenger = raw.challenger === null || raw.challenger === undefined ? null : modelSummary(raw.challenger);
  const c = isObj(raw.comparison) ? raw.comparison : {};
  const decision = c.decision === "promote_challenger" || c.decision === "insufficient_data" ? c.decision : "keep_champion";
  const r = isObj(raw.reliability) ? raw.reliability : {};
  const bins = (Array.isArray(r.bins) ? r.bins : []).filter(
    (b): b is { p_mean: number; observed: number; n: number } => isObj(b) && isProb(b.p_mean) && isProb(b.observed) && isNum(b.n),
  );
  return {
    generated_at: raw.generated_at,
    champion,
    challenger,
    comparison: {
      horizon: isNum(c.horizon) ? c.horizon : 30,
      delta_brier: isNum(c.delta_brier) ? c.delta_brier : 0,
      delta_log_loss: isNum(c.delta_log_loss) ? c.delta_log_loss : 0,
      ci_delta_brier: pairOrNull(c.ci_delta_brier),
      decision,
      note: isStr(c.note) ? c.note : "",
    },
    reliability: { horizon: isNum(r.horizon) ? r.horizon : 30, bins },
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
    typeof v.robots_changed === "boolean"
  );
}

export function validateSourceHealth(raw: unknown): { data: SourceHealthResponse; discarded: number } {
  if (!isObj(raw) || !isIsoDate(raw.generated_at) || !Array.isArray(raw.sources)) {
    throw new InvalidResponseError("/source-health", "formato inesperado");
  }
  const sources = raw.sources.filter(isSource).map((s) => ({
    ...s,
    last_success_at: isoOrNull(s.last_success_at),
    last_item_at: isoOrNull(s.last_item_at),
    items_new_24h: numOrNull(s.items_new_24h),
    items_new_7d: numOrNull(s.items_new_7d),
    extraction_rate_7d: isProb(s.extraction_rate_7d) ? s.extraction_rate_7d : null,
    error_rate_24h: isProb(s.error_rate_24h) ? s.error_rate_24h : 0,
    robots_hash: strOrNull(s.robots_hash),
    message: strOrNull(s.message),
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

const EMPTY_H = { n: 0, hit_rate: 0, brier: 0, log_loss: 0 };

export function validateAccuracy(raw: unknown): { data: AccuracyResponse; discarded: number; discardedWeekly: number } {
  if (!isObj(raw) || !isIsoDate(raw.generated_at)) {
    throw new InvalidResponseError("/prediction-log/accuracy", "formato inesperado");
  }
  // Janelas sem predições resolvidas podem faltar na API; viram n = 0.
  const got = horizonMetrics<AccuracyResponse["by_horizon"][Horizon]>(raw.by_horizon, ["n", "hit_rate", "brier", "log_loss"]);
  const by_horizon = { "7": got["7"] ?? EMPTY_H, "15": got["15"] ?? EMPTY_H, "30": got["30"] ?? EMPTY_H };
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
  return {
    data: { generated_at: raw.generated_at, period: periodOrNull(raw.period), by_horizon, weekly, alerts },
    discarded: rawAlerts.length - alerts.length,
    discardedWeekly: rawWeekly.length - weekly.length,
  };
}

function isThresholdAlert(v: unknown): v is ThresholdAlert {
  return (
    isObj(v) &&
    isIsoDate(v.made_at) &&
    isObj(v.pair) && isStr(v.pair.origin) && isStr(v.pair.destination) &&
    isStr(v.type) && OFFER_TYPES.has(v.type) &&
    isNum(v.horizon_days) &&
    isProb(v.probability) &&
    (v.previous_probability === null || v.previous_probability === undefined || isProb(v.previous_probability)) &&
    isProb(v.threshold)
  );
}

export function validateThresholdAlerts(raw: unknown): { data: ThresholdAlertsResponse; discarded: number } {
  if (!isObj(raw) || !isIsoDate(raw.generated_at) || !Array.isArray(raw.items)) {
    throw new InvalidResponseError("/alerts", "formato inesperado");
  }
  const items = raw.items.filter(isThresholdAlert).map((a) => ({ ...a, previous_probability: a.previous_probability ?? null }));
  return { data: { generated_at: raw.generated_at, items }, discarded: raw.items.length - items.length };
}

export function validateExplanation(raw: unknown): Explanation {
  if (!isObj(raw) || !isObj(raw.pair) || !isStr(raw.pair.origin) || !isStr(raw.pair.destination) || !isStr(raw.type) || !OFFER_TYPES.has(raw.type)) {
    throw new InvalidResponseError("/predictions/explanation", "formato inesperado");
  }
  const f = isObj(raw.factors) ? raw.factors : {};
  const w = isObj(raw.windows) ? raw.windows : {};
  const windows: Explanation["windows"] = {};
  for (const h of HORIZON_KEYS) if (isProb(w[h])) windows[h] = w[h];
  return {
    pair: { origin: raw.pair.origin, destination: raw.pair.destination },
    type: raw.type as Explanation["type"],
    as_of: isIsoDate(raw.as_of) ? raw.as_of : "",
    windows,
    factors: {
      method: methodOrNull(f.method),
      probability_driven_by: strOrNull(f.probability_driven_by),
      n_campaigns: Number.isInteger(f.n_campaigns) && (f.n_campaigns as number) >= 0 ? (f.n_campaigns as number) : null,
      last_campaign_start: isoOrNull(f.last_campaign_start),
      days_since_last: numOrNull(f.days_since_last),
      median_interval_days: numOrNull(f.median_interval_days),
      min_campaigns_b1: numOrNull(f.min_campaigns_b1),
    },
  };
}

export function validateStatus(raw: unknown): StatusResponse {
  if (!isObj(raw) || !isIsoDate(raw.generated_at) || !isObj(raw.stop) || typeof raw.stop.active !== "boolean") {
    throw new InvalidResponseError("/status", "formato inesperado");
  }
  const lj = isObj(raw.last_job) ? raw.last_job : null;
  return {
    generated_at: raw.generated_at,
    stop: { active: raw.stop.active, source: strOrNull(raw.stop.source), since: isoOrNull(raw.stop.since) },
    last_job: lj ? { run_at: isoOrNull(lj.run_at), model_run_id: strOrNull(lj.model_run_id), status: strOrNull(lj.status) } : null,
    n_campaigns_total: Number.isInteger(raw.n_campaigns_total) ? (raw.n_campaigns_total as number) : null,
  };
}
