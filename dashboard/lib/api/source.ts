import "server-only";

export type DataSource = "mock" | "api";

/**
 * Decide de onde vêm os dados. Tudo lido de variáveis de ambiente no servidor;
 * a chave nunca chega ao cliente.
 */
export function resolveDataSource(): DataSource {
  const forced = process.env.PREDITOR_DATA_SOURCE;
  if (forced === "api" || forced === "mock") return forced;
  return process.env.PREDITOR_API_BASE_URL ? "api" : "mock";
}

export function apiConfig(): { baseUrl: string; apiKey: string } {
  const baseUrl = process.env.PREDITOR_API_BASE_URL?.replace(/\/+$/, "");
  const apiKey = process.env.PREDITOR_API_KEY;
  if (!baseUrl) throw new Error("PREDITOR_API_BASE_URL ausente");
  if (!apiKey) throw new Error("PREDITOR_API_KEY ausente");
  return { baseUrl, apiKey };
}
