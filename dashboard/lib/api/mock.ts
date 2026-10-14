import "server-only";
import predictions from "@/mock/predictions.json";
import modelMetrics from "@/mock/model-metrics.json";
import sourceHealth from "@/mock/source-health.json";
import accuracy from "@/mock/prediction-log-accuracy.json";
import alerts from "@/mock/alerts.json";
import status from "@/mock/status.json";
import explanations from "@/mock/explanations.json";

// Os JSON seguem o contrato; cada um passa pela mesma validação da API real.
export const mockPredictions: unknown = predictions;
export const mockModelMetrics: unknown = modelMetrics;
export const mockSourceHealth: unknown = sourceHealth;
export const mockAccuracy: unknown = accuracy;
export const mockAlerts: unknown = alerts;
export const mockStatus: unknown = status;
export const mockExplanations: unknown = explanations;
