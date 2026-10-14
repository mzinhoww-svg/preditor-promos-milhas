import "server-only";
import { ApiError, getJson } from "./http";
import {
  mockAccuracy,
  mockAlerts,
  mockExplanations,
  mockModelMetrics,
  mockPredictions,
  mockSourceHealth,
  mockStatus,
} from "./mock";
import { ApiConfigError, resolveDataSource, type DataSource } from "./source";
import type {
  AccuracyResponse,
  Explanation,
  ModelMetricsResponse,
  OfferType,
  PredictionsResponse,
  SourceHealthResponse,
  StatusResponse,
  ThresholdAlertsResponse,
} from "./types";
import {
  InvalidResponseError,
  validateAccuracy,
  validateExplanation,
  validateModelMetrics,
  validatePredictions,
  validateSourceHealth,
  validateStatus,
  validateThresholdAlerts,
} from "./validate";

export type { DataSource };
export { ApiError, ApiConfigError, InvalidResponseError };
export * from "./types";

/** Motivo de a tela estar em dados simulados mesmo com API configurada. */
export interface Fallback {
  code: string;
  message: string;
  status: number | null;
}

/**
 * Resultado de carga: dados validados, nº de itens descartados por formato (D4),
 * origem real dos dados e, se a API falhou, o motivo da queda para dados simulados.
 */
export interface Loaded<T> {
  data: T;
  discarded: number;
  origin: DataSource;
  fallback: Fallback | null;
}

/** Endpoint opcional (ainda não existe em toda versão da API): dados ou motivo da ausência. */
export interface Optional<T> {
  data: T | null;
  discarded: number;
  origin: DataSource;
  unavailable: Fallback | null;
}

export function dataSource(): DataSource {
  return resolveDataSource();
}

function toFallback(err: unknown): Fallback {
  if (err instanceof ApiError) return { code: err.code, message: err.message, status: err.status };
  if (err instanceof InvalidResponseError) return { code: "invalid_response", message: err.message, status: null };
  if (err instanceof ApiConfigError) return { code: "config", message: err.message, status: null };
  return { code: "unknown", message: err instanceof Error ? err.message : "erro desconhecido", status: null };
}

/**
 * Camada de acesso a dados. As telas só conhecem estas funções; trocar de
 * mock para API é mudar variável de ambiente (ver docs/api-contract.md).
 * Com a API configurada, qualquer falha (rede, HTTP, JSON, validação) cai
 * para os dados simulados e devolve o motivo, que a tela mostra em destaque.
 */
async function load<T>(
  path: string,
  mock: unknown,
  validate: (raw: unknown) => { data: T; discarded: number },
  query?: Record<string, string | undefined>,
): Promise<Loaded<T>> {
  if (dataSource() === "api") {
    try {
      const v = validate(await getJson<unknown>(path, query));
      return { ...v, origin: "api", fallback: null };
    } catch (err) {
      const v = validate(mock);
      return { ...v, origin: "mock", fallback: toFallback(err) };
    }
  }
  const v = validate(mock);
  return { ...v, origin: "mock", fallback: null };
}

async function loadOptional<T>(
  path: string,
  mock: unknown,
  validate: (raw: unknown) => { data: T; discarded: number },
  query?: Record<string, string | undefined>,
): Promise<Optional<T>> {
  if (dataSource() === "api") {
    try {
      const v = validate(await getJson<unknown>(path, query));
      return { ...v, origin: "api", unavailable: null };
    } catch (err) {
      return { data: null, discarded: 0, origin: "api", unavailable: toFallback(err) };
    }
  }
  const v = validate(mock);
  return { ...v, origin: "mock", unavailable: null };
}

export async function getPredictions(opts?: { type?: OfferType; limit?: number }): Promise<Loaded<PredictionsResponse>> {
  const res = await load("/predictions", mockPredictions, validatePredictions, { type: opts?.type, limit: opts?.limit?.toString() });
  // Em modo mock o filtro é local; a API já filtra, mas repetir não custa.
  const items = res.data.items.filter((i) => !opts?.type || i.type === opts.type).slice(0, opts?.limit ?? 50);
  return { ...res, data: { ...res.data, items } };
}

export async function getModelMetrics(): Promise<Loaded<ModelMetricsResponse>> {
  return load("/model/metrics", mockModelMetrics, (raw) => ({ data: validateModelMetrics(raw), discarded: 0 }));
}

export async function getSourceHealth(): Promise<Loaded<SourceHealthResponse>> {
  return load("/source-health", mockSourceHealth, validateSourceHealth);
}

/** F3: além dos alertas descartados, conta as semanas de `weekly` descartadas. */
export async function getAccuracy(
  opts?: { from?: string; to?: string; horizon?: string },
): Promise<Loaded<AccuracyResponse> & { discardedWeekly: number }> {
  if (dataSource() === "api") {
    try {
      const v = validateAccuracy(await getJson<unknown>("/prediction-log/accuracy", opts));
      return { ...v, origin: "api", fallback: null };
    } catch (err) {
      return { ...validateAccuracy(mockAccuracy), origin: "mock", fallback: toFallback(err) };
    }
  }
  return { ...validateAccuracy(mockAccuracy), origin: "mock", fallback: null };
}

/** GET /v1/alerts (T10b). Ausente na API da main até o PR #50 entrar: a tela avisa, sem cair. */
export async function getThresholdAlerts(limit = 100): Promise<Optional<ThresholdAlertsResponse>> {
  return loadOptional("/alerts", mockAlerts, validateThresholdAlerts, { limit: String(limit) });
}

/** GET /v1/status (proposto no contrato). 404 vira "não exposto"; a tela mostra o estado como desconhecido. */
export async function getStatus(): Promise<Optional<StatusResponse>> {
  return loadOptional("/status", mockStatus, (raw) => ({ data: validateStatus(raw), discarded: 0 }));
}

/**
 * Explicação por item (T10b), carregada sob demanda pela rota /api/explanation
 * para não multiplicar chamadas à API (limite de 60/min por chave).
 */
export async function getExplanation(origin: string, destination: string, type: OfferType): Promise<Optional<Explanation>> {
  if (dataSource() === "api") {
    const path = `/predictions/${encodeURIComponent(origin)}/${encodeURIComponent(destination)}/explanation`;
    try {
      return { data: validateExplanation(await getJson<unknown>(path, { type })), discarded: 0, origin: "api", unavailable: null };
    } catch (err) {
      return { data: null, discarded: 0, origin: "api", unavailable: toFallback(err) };
    }
  }
  const key = `${origin}|${destination}|${type}`;
  const raw = (mockExplanations as Record<string, unknown>)[key];
  if (!raw) return { data: null, discarded: 0, origin: "mock", unavailable: { code: "not_found", message: "sem explicação registrada", status: 404 } };
  return { data: validateExplanation(raw), discarded: 0, origin: "mock", unavailable: null };
}
