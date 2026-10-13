import "server-only";
import predictions from "@/mock/predictions.json";
import modelMetrics from "@/mock/model-metrics.json";
import sourceHealth from "@/mock/source-health.json";
import accuracy from "@/mock/prediction-log-accuracy.json";
import type {
  AccuracyResponse,
  ModelMetricsResponse,
  PredictionsResponse,
  SourceHealthResponse,
} from "./types";

// Os JSON seguem o contrato à risca; a asserção fixa o tipo nominal (enums).
export const mockPredictions = predictions as PredictionsResponse;
export const mockModelMetrics = modelMetrics as ModelMetricsResponse;
export const mockSourceHealth = sourceHealth as SourceHealthResponse;
export const mockAccuracy = accuracy as AccuracyResponse;
