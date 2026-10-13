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
  ci_low: number;
  ci_high: number;
}

export interface Reason {
  kind: ReasonKind;
  label: string;
  detail: string | null;
  weight: number;
}

export interface PredictionItem {
  rank: number;
  pair: { origin: string; destination: string };
  type: OfferType;
  segmented: boolean;
  segment_label: string | null;
  windows: Record<Horizon, WindowProbability>;
  bonus_pct: { p25: number; p50: number; p75: number };
  last_offer: {
    start_at: string;
    end_at: string | null;
    bonus_pct: number;
    days_since: number;
  } | null;
  reasons: Reason[];
}

export interface PredictionsResponse {
  generated_at: string;
  model: { run_id: string; name: string; version: string; role: "champion" | "challenger" };
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
    period: { from: string; to: string };
    by_horizon: Record<Horizon, ValidationMetrics>;
  };
  production: {
    period: { from: string; to: string };
    n_predictions: number;
    n_resolved: number;
    by_horizon: Record<Horizon, ProductionMetrics>;
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
  items_new_24h: number;
  items_new_7d: number;
  extraction_rate_7d: number;
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
  period: { from: string; to: string };
  by_horizon: Record<Horizon, { n: number; hit_rate: number; brier: number; log_loss: number }>;
  weekly: { week: string; horizon: number; n: number; hit_rate: number; brier: number }[];
  alerts: Alert[];
}
