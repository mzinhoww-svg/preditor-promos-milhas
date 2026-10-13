import "server-only";
import { getJson } from "./http";
import { mockAccuracy, mockModelMetrics, mockPredictions, mockSourceHealth } from "./mock";
import { resolveDataSource, type DataSource } from "./source";
import type {
  AccuracyResponse,
  ModelMetricsResponse,
  OfferType,
  PredictionsResponse,
  SourceHealthResponse,
} from "./types";

export type { DataSource };
export * from "./types";

/**
 * Camada de acesso a dados. As telas só conhecem estas funções; trocar de
 * mock para API é mudar variável de ambiente (ver docs/api-contract.md).
 */
export function dataSource(): DataSource {
  return resolveDataSource();
}

export async function getPredictions(opts?: { type?: OfferType; limit?: number }): Promise<PredictionsResponse> {
  if (dataSource() === "api") {
    return getJson<PredictionsResponse>("/predictions", {
      type: opts?.type,
      limit: opts?.limit?.toString(),
    });
  }
  const items = mockPredictions.items
    .filter((i) => !opts?.type || i.type === opts.type)
    .slice(0, opts?.limit ?? 50);
  return { ...mockPredictions, items };
}

export async function getModelMetrics(): Promise<ModelMetricsResponse> {
  if (dataSource() === "api") return getJson<ModelMetricsResponse>("/model/metrics");
  return mockModelMetrics;
}

export async function getSourceHealth(): Promise<SourceHealthResponse> {
  if (dataSource() === "api") return getJson<SourceHealthResponse>("/source-health");
  return mockSourceHealth;
}

export async function getAccuracy(opts?: { from?: string; to?: string; horizon?: string }): Promise<AccuracyResponse> {
  if (dataSource() === "api") return getJson<AccuracyResponse>("/prediction-log/accuracy", opts);
  return mockAccuracy;
}
