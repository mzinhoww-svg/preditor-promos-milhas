import "server-only";
import { ApiError, getJson } from "./http";
import { mockAccuracy, mockModelMetrics, mockPredictions, mockSourceHealth } from "./mock";
import { resolveDataSource, type DataSource } from "./source";
import type { AccuracyResponse, ModelMetricsResponse, OfferType, PredictionsResponse, SourceHealthResponse } from "./types";
import {
  InvalidResponseError,
  validateAccuracy,
  validateModelMetrics,
  validatePredictions,
  validateSourceHealth,
} from "./validate";

export type { DataSource };
export { ApiError, InvalidResponseError };
export * from "./types";

/** Resposta mais o número de itens descartados por formato inválido (D4). */
export type Validated<T> = { data: T; discarded: number };

/**
 * Camada de acesso a dados. As telas só conhecem estas funções; trocar de
 * mock para API é mudar variável de ambiente (ver docs/api-contract.md).
 * Toda resposta (mock ou API) passa pela mesma validação.
 */
export function dataSource(): DataSource {
  return resolveDataSource();
}

async function load<T>(path: string, mock: unknown, query?: Record<string, string | undefined>): Promise<T> {
  if (dataSource() === "api") return getJson<T>(path, query);
  return mock as T;
}

export async function getPredictions(opts?: { type?: OfferType; limit?: number }): Promise<Validated<PredictionsResponse>> {
  const raw = await load<unknown>("/predictions", mockPredictions, { type: opts?.type, limit: opts?.limit?.toString() });
  const { data, discarded } = validatePredictions(raw);
  // Em modo mock o filtro é local; a API já filtra, mas repetir não custa.
  const items = data.items.filter((i) => !opts?.type || i.type === opts.type).slice(0, opts?.limit ?? 50);
  return { data: { ...data, items }, discarded };
}

export async function getModelMetrics(): Promise<ModelMetricsResponse> {
  return validateModelMetrics(await load<unknown>("/model/metrics", mockModelMetrics));
}

export async function getSourceHealth(): Promise<Validated<SourceHealthResponse>> {
  return validateSourceHealth(await load<unknown>("/source-health", mockSourceHealth));
}

export async function getAccuracy(opts?: { from?: string; to?: string; horizon?: string }): Promise<Validated<AccuracyResponse>> {
  return validateAccuracy(await load<unknown>("/prediction-log/accuracy", mockAccuracy, opts));
}
