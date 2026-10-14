"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { Explanation, Method, OfferType } from "@/lib/api/types";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; data: Explanation; origin: "mock" | "api" }
  | { kind: "missing" }
  | { kind: "error"; message: string };

const DRIVER_LABEL: Record<string, string> = {
  base_rate: "taxa-base histórica do par",
  seasonal_hazard: "hazard empírico por intervalo e mês",
};

const METHOD_LABEL: Record<Method, string> = { b0: "B0 · taxa-base", b1: "B1 · hazard empírico" };

function ptDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(d);
}

/**
 * Explicação do item (T10b), carregada só quando o leitor abre o bloco, por uma
 * rota do próprio dashboard (a chave da API nunca chega aqui).
 */
export function ExplanationPanel({
  origin,
  destination,
  type,
  summaryHint,
  children,
}: {
  origin: string;
  destination: string;
  type: OfferType;
  summaryHint: string | null;
  children?: ReactNode;
}) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const ref = useRef<HTMLDetailsElement>(null);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const qs = new URLSearchParams({ origin, destination, type });
      const res = await fetch(`/api/explanation?${qs}`, { headers: { Accept: "application/json" } });
      if (res.status === 404) return setState({ kind: "missing" });
      const body = (await res.json()) as { data: Explanation | null; origin: "mock" | "api"; error?: { message?: string } };
      if (!res.ok || !body.data) return setState({ kind: "error", message: body.error?.message ?? `HTTP ${res.status}` });
      setState({ kind: "ready", data: body.data, origin: body.origin });
    } catch {
      setState({ kind: "error", message: "falha de rede" });
    }
  }, [origin, destination, type]);

  // Bloco já aberto na hidratação (estado restaurado pelo navegador): carrega sem esperar o toggle.
  useEffect(() => {
    if (ref.current?.open && state.kind === "idle") void load();
  }, [load, state.kind]);

  return (
    <details
      ref={ref}
      className="group rounded-md border border-line bg-surface-2 open:bg-bg"
      onToggle={(e) => {
        if ((e.currentTarget as HTMLDetailsElement).open && state.kind === "idle") void load();
      }}
    >
      <summary className="flex min-w-0 cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm text-ink-2 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2">
        <span className="min-w-0 truncate">
          <span className="font-medium text-ink">Por que está na lista</span>
          {summaryHint ? `: ${summaryHint}` : ""}
        </span>
        <span aria-hidden="true" className="shrink-0 text-xs text-ink-3 group-open:hidden">
          ver fatores
        </span>
        <span aria-hidden="true" className="hidden shrink-0 text-xs text-ink-3 group-open:inline">
          ocultar
        </span>
      </summary>
      <div className="border-t border-line px-3 py-3">
        <Body state={state} onRetry={load} />
        {children}
      </div>
    </details>
  );
}

function Body({ state, onRetry }: { state: State; onRetry: () => void }) {
  if (state.kind === "idle" || state.kind === "loading") {
    return (
      <div aria-busy="true" aria-live="polite" className="flex flex-col gap-2">
        <span className="sr-only">Carregando explicação</span>
        <span aria-hidden="true" className="block h-3.5 w-2/3 animate-pulse rounded bg-line motion-reduce:animate-none" />
        <span aria-hidden="true" className="block h-3.5 w-1/2 animate-pulse rounded bg-line motion-reduce:animate-none" />
        <span aria-hidden="true" className="block h-3.5 w-1/3 animate-pulse rounded bg-line motion-reduce:animate-none" />
      </div>
    );
  }
  if (state.kind === "missing") {
    return <p className="text-sm text-ink-2">Sem explicação registrada para este item na última execução do job.</p>;
  }
  if (state.kind === "error") {
    return (
      <p className="text-sm text-ink-2" role="alert">
        Explicação indisponível ({state.message}).{" "}
        <button type="button" onClick={onRetry} className="font-medium text-primary underline underline-offset-2">
          Tentar de novo
        </button>
      </p>
    );
  }
  const f = state.data.factors;
  const method = f.method;
  const min = f.min_campaigns_b1 ?? 25;
  return (
    <div className="flex flex-col gap-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        {method ? (
          <span
            className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium leading-4 ${
              method === "b1" ? "border-primary/30 bg-primary-soft text-primary" : "border-line bg-surface-2 text-ink-2"
            }`}
          >
            {METHOD_LABEL[method]}
          </span>
        ) : null}
        <span className="text-ink">
          Baseado em{" "}
          <span className="tnum font-semibold">{f.n_campaigns ?? "—"}</span> campanhas históricas
          {f.n_campaigns !== null && f.n_campaigns < min ? (
            <span className="text-ink-2"> · abaixo das {min} que o B1 exige, por isso taxa-base</span>
          ) : null}
        </span>
      </div>
      <dl className="grid grid-cols-[repeat(auto-fit,minmax(10rem,1fr))] gap-x-6 gap-y-2">
        <div>
          <dt className="text-xs text-ink-3">Última campanha</dt>
          <dd className="text-ink">
            {ptDate(f.last_campaign_start)}
            {f.days_since_last !== null ? <span className="text-ink-2"> · há {f.days_since_last} dias</span> : null}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3">Intervalo mediano entre campanhas</dt>
          <dd className="text-ink">{f.median_interval_days !== null ? `${f.median_interval_days} dias` : "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3">Probabilidade vem de</dt>
          <dd className="text-ink">{f.probability_driven_by ? (DRIVER_LABEL[f.probability_driven_by] ?? f.probability_driven_by) : "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3">Calculado em</dt>
          <dd className="text-ink">{ptDate(state.data.as_of || null)}</dd>
        </div>
      </dl>
      {state.origin === "mock" ? <p className="text-xs text-warn">Explicação de exemplo (dados simulados).</p> : null}
    </div>
  );
}
