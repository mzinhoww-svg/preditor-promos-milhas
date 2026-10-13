import "server-only";
import { apiConfig } from "./source";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** GET autenticado contra a API da VPS. Header X-API-Key vem só do ambiente. */
export async function getJson<T>(path: string, query?: Record<string, string | undefined>): Promise<T> {
  const { baseUrl, apiKey } = apiConfig();
  const url = new URL(baseUrl + path);
  for (const [k, v] of Object.entries(query ?? {})) if (v) url.searchParams.set(k, v);

  const res = await fetch(url, {
    headers: { "X-API-Key": apiKey, Accept: "application/json" },
    next: { revalidate: 300 },
  });

  if (!res.ok) {
    let code = "http_error";
    let message = `HTTP ${res.status}`;
    try {
      const body = (await res.json()) as { error?: { code?: string; message?: string } };
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {
      // corpo não JSON: mantém o padrão
    }
    throw new ApiError(res.status, code, message);
  }
  return (await res.json()) as T;
}
