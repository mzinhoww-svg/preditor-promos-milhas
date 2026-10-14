import "server-only";

export type DataSource = "mock" | "api";

/**
 * Base da API. Aceita PREDITOR_API_BASE_URL (preferida) ou NEXT_PUBLIC_API_BASE_URL.
 * As duas são lidas só no servidor; a chave (PREDITOR_API_KEY) nunca tem prefixo
 * NEXT_PUBLIC_ e nunca chega ao bundle do cliente.
 */
export function apiBaseUrl(): string | null {
  const raw = process.env.PREDITOR_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "";
  const base = raw.trim().replace(/\/+$/, "");
  return base ? base : null;
}

/**
 * Decide de onde vêm os dados. `PREDITOR_DATA_SOURCE=mock` força dados simulados;
 * `api` força a API; sem a variável, usa a API quando há base configurada.
 */
export function resolveDataSource(): DataSource {
  const forced = process.env.PREDITOR_DATA_SOURCE;
  if (forced === "api" || forced === "mock") return forced;
  return apiBaseUrl() ? "api" : "mock";
}

export class ApiConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiConfigError";
  }
}

export function apiConfig(): { baseUrl: string; apiKey: string } {
  const baseUrl = apiBaseUrl();
  const apiKey = process.env.PREDITOR_API_KEY?.trim();
  if (!baseUrl) throw new ApiConfigError("PREDITOR_API_BASE_URL ausente");
  if (!apiKey) throw new ApiConfigError("PREDITOR_API_KEY ausente");
  return { baseUrl, apiKey };
}
