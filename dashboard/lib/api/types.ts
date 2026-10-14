// Tipos espelham docs/api-contract.md. Mudança aqui exige mudança no contrato.

export type Horizon = "7" | "15" | "30";
export const HORIZONS: Horizon[] = ["7", "15", "30"];

export type OfferType = "transfer_bonus" | "purchase_discount" | "boosted_accrual";

export type ReasonKind =
  | "days_since_last"
  | "month"
  | "sibling_pairs"
  | "source_signal"
  | "other";

export interface WindowProbability {
  probability: number;
  /** A API de produção ainda não calcula IC: vem igual à probabilidade e a tela mostra "IC indisponível". */
  ci_low: number;
  ci_high: number;
}

export interface Reason {
  kind: ReasonKind;
  label: string;
  detail: string | null;
  weight: number;
}

/** Método que gerou a predição do item. Só B0 (taxa-base) e B1 (hazard empírico) existem em produção. */
export type Method = "b0" | "b1";

export interface PredictionItem {
  rank: number;
  pair: { origin: string; destination: string };
  type: OfferType;
  segmented: boolean;
  segment_label: string | null;
  /** Janela malformada vira null e é sinalizada na tela; o item fica (ressalva 4 do QA). */
  windows: Record<Horizon, WindowProbability | null>;
  /** Quartis do bônus; null quando o par não tem histórico de bônus. */
  bonus_pct: { p25: number | null; p50: number | null; p75: number | null };
  last_offer: {
    start_at: string;
    end_at: string | null;
    bonus_pct: number;
    days_since: number;
  } | null;
  reasons: Reason[];
  /** Proposto no contrato (ainda não servido pela API): método e nº de campanhas do item. */
  method: Method | null;
  n_campaigns: number | null;
}

export interface PredictionsResponse {
  generated_at: string;
  model: { run_id: string; name: string; version: string | null; role: "champion" | "challenger" };
  items: PredictionItem[];
}

export interface ValidationMetrics {
  brier: number;
  log_loss: number;
  auc: number;
  /** Pode vir ausente na API; a tela mostra "—". */
  ci_brier: [number, number] | null;
}

export interface ProductionMetrics {
  brier: number;
  log_loss: number;
  hit_rate: number;
  n: number;
}

export interface ModelSummary {
  name: string;
  version: string;
  trained_at: string;
  horizons: number[];
  validation: {
    method: string;
    /** F2: null quando a API não manda um inteiro positivo. */
    folds: number | null;
    /** null enquanto o modelo não tiver validação histórica registrada. */
    period: { from: string | null; to: string | null };
    /** Janelas sem métrica ficam ausentes; a tela mostra "—". */
    by_horizon: Partial<Record<Horizon, ValidationMetrics>>;
  };
  production: {
    period: { from: string | null; to: string | null };
    n_predictions: number;
    n_resolved: number;
    by_horizon: Partial<Record<Horizon, ProductionMetrics>>;
  } | null;
}

export type ComparisonDecision = "keep_champion" | "promote_challenger" | "insufficient_data";

export interface ModelMetricsResponse {
  generated_at: string;
  champion: ModelSummary;
  challenger: ModelSummary | null;
  comparison: {
    horizon: number;
    delta_brier: number;
    delta_log_loss: number;
    ci_delta_brier: [number, number] | null;
    decision: ComparisonDecision;
    note: string;
    /** false quando a API ainda não comparou nada (nota "sem dados", IC [0,0] e Δ 0): a tela diz "sem dados". */
    has_data: boolean;
  };
  reliability: {
    horizon: number;
    bins: { p_mean: number; observed: number; n: number }[];
  };
}

export type SourceStatus = "ok" | "degraded" | "stale" | "blocked" | "error";
export type SourceKind = "rss" | "html" | "wayback" | "official";

export interface SourceHealth {
  source: string;
  kind: SourceKind;
  status: SourceStatus;
  last_success_at: string | null;
  last_item_at: string | null;
  items_new_24h: number | null;
  items_new_7d: number | null;
  extraction_rate_7d: number | null;
  error_rate_24h: number;
  robots_hash: string | null;
  robots_changed: boolean;
  message: string | null;
}

export interface SourceHealthResponse {
  generated_at: string;
  sources: SourceHealth[];
}

export type AlertSeverity = "info" | "warning" | "critical";
export type AlertKind = "drift" | "source" | "budget" | "pipeline" | "model";

export interface Alert {
  id: string;
  severity: AlertSeverity;
  kind: AlertKind;
  title: string;
  detail: string;
  since: string;
  related: { horizon: number | null; source: string | null; pair: string | null };
}

export interface AccuracyResponse {
  generated_at: string;
  period: { from: string | null; to: string | null };
  by_horizon: Record<Horizon, { n: number; hit_rate: number; brier: number; log_loss: number }>;
  weekly: { week: string; horizon: number; n: number; hit_rate: number; brier: number }[];
  alerts: Alert[];
}

/** GET /v1/alerts (T10b): cruzamentos de limiar de probabilidade registrados pelo job diário. */
export interface ThresholdAlert {
  made_at: string;
  pair: { origin: string; destination: string };
  type: OfferType;
  horizon_days: number;
  probability: number;
  previous_probability: number | null;
  threshold: number;
}

export interface ThresholdAlertsResponse {
  generated_at: string;
  items: ThresholdAlert[];
}

/** GET /v1/predictions/{origin}/{destination}/explanation (T10b): fatores point-in-time do item. */
export interface Explanation {
  pair: { origin: string; destination: string };
  type: OfferType;
  as_of: string;
  windows: Partial<Record<Horizon, number>>;
  factors: {
    method: Method | null;
    probability_driven_by: string | null;
    n_campaigns: number | null;
    last_campaign_start: string | null;
    days_since_last: number | null;
    median_interval_days: number | null;
    min_campaigns_b1: number | null;
  };
}

/** GET /v1/status (proposto): estado de operação. 404 = API ainda não expõe. */
export interface StatusResponse {
  generated_at: string;
  stop: { active: boolean; source: string | null; since: string | null };
  last_job: { run_at: string | null; model_run_id: string | null; status: string | null } | null;
  n_campaigns_total: number | null;
}
