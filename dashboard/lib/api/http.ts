import "server-only";
import { apiConfig } from "./source";

/** D5: API lenta não pode pendurar a tela. */
const TIMEOUT_MS = 8000;

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

/**
 * Opções de fetch: sem cache de dados. Com `revalidate` a Vercel servia uma resposta
 * boa por até 5 min depois de a API cair, com badge "API" e sem aviso (ressalva 3 do QA).
 * O custo é 3–4 chamadas por tela, dentro do limite de 60/min por chave.
 */
export const FETCH_INIT: RequestInit = { cache: "no-store" };

/** GET autenticado contra a API da VPS. Header X-API-Key vem só do ambiente. */
export async function getJson<T>(path: string, query?: Record<string, string | undefined>): Promise<T> {
  const { baseUrl, apiKey } = apiConfig();
  const url = new URL(baseUrl + path);
  for (const [k, v] of Object.entries(query ?? {})) if (v) url.searchParams.set(k, v);

  let res: Response;
  try {
    res = await fetch(url, {
      ...FETCH_INIT,
      headers: { "X-API-Key": apiKey, Accept: "application/json" },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    const name = err instanceof Error ? err.name : "";
    if (name === "TimeoutError" || name === "AbortError") {
      throw new ApiError(504, "timeout", `API não respondeu em ${TIMEOUT_MS / 1000} s`);
    }
    throw new ApiError(502, "network_error", "Falha de rede ao chamar a API");
  }

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
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError(502, "invalid_json", "Resposta da API não é JSON");
  }
}
