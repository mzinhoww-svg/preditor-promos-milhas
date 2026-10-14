import type { Fallback } from "@/lib/api";

/** Só cargas obrigatórias (Loaded) entram aqui; endpoints opcionais não decidem o aviso. */
export interface OriginInfo {
  origin: "mock" | "api";
  fallback: Fallback | null;
}

const CODE_LABEL: Record<string, string> = {
  timeout: "a API não respondeu a tempo",
  network_error: "falha de rede ao chamar a API",
  invalid_json: "a API devolveu um corpo que não é JSON",
  invalid_response: "a resposta da API não segue o contrato",
  config: "configuração incompleta no servidor",
  http_error: "a API devolveu erro HTTP",
};

export function fallbackReason(f: Fallback): string {
  const base = CODE_LABEL[f.code] ?? "a API devolveu erro";
  // Só o erro HTTP real da API leva o código; timeout e rede têm status sintético.
  return f.code === "http_error" && f.status ? `${base} (HTTP ${f.status})` : base;
}

/**
 * Aviso de dados simulados. Aparece sempre que a tela mostra dados de exemplo,
 * seja por configuração (sem API) ou por queda da API com fallback.
 */
export function DataNotice({ sources, configured }: { sources: OriginInfo[]; configured: "mock" | "api" }) {
  const fallbacks = sources.map((s) => s.fallback).filter((f): f is Fallback => !!f);
  const simulated = configured === "mock" || sources.some((s) => s.origin === "mock");
  if (!simulated) return null;
  // "em parte" só quando alguma carga obrigatória veio mesmo da API.
  const partial = configured === "api" && sources.some((s) => s.origin === "api" && !s.fallback);
  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-6 flex flex-col gap-1 rounded-lg border border-warn/40 bg-warn-soft px-4 py-3 text-sm text-warn"
    >
      <p className="font-semibold">
        Dados simulados
        {partial ? " em parte desta tela" : ""}
      </p>
      {configured === "mock" ? (
        <p className="text-ink-2">
          O painel está em modo de exemplo: nenhuma API configurada. Os números são ilustrativos e não devem orientar
          decisões.
        </p>
      ) : (
        <p className="text-ink-2">
          A API está configurada, mas {fallbacks.length ? fallbackReason(fallbacks[0]) : "não respondeu"}. Até ela voltar, esta
          tela mostra dados de exemplo; não use estes números para decidir.
        </p>
      )}
    </div>
  );
}
