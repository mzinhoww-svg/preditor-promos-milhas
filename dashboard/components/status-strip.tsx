import { Badge } from "@/components/badge";
import { fallbackReason } from "@/components/data-notice";
import type { Optional, StatusResponse } from "@/lib/api";
import { dateTime, int, relativeFrom, timeUTC } from "@/lib/format";

/**
 * Faixa de operação: estado STOP, última execução do job diário e base
 * histórica. Vem de GET /v1/status; quando a API ainda não expõe a rota, diz
 * isso em vez de presumir que está tudo bem.
 */
export function StatusStrip({ status, jobFallbackAt, now }: { status: Optional<StatusResponse>; jobFallbackAt: string | null; now: Date }) {
  const s = status.data;
  const runAt = s?.last_job?.run_at ?? jobFallbackAt;
  return (
    <dl
      aria-label="Estado da operação"
      className="mb-6 grid grid-cols-[repeat(auto-fit,minmax(11rem,1fr))] gap-x-6 gap-y-3 rounded-lg border border-line px-4 py-3 text-sm"
    >
      <div className="min-w-0">
        <dt className="text-xs text-ink-3">Parada de emergência (STOP)</dt>
        <dd className="mt-1 flex flex-wrap items-center gap-2">
          {s ? (
            s.stop.active ? (
              <>
                <Badge tone="crit">STOP ativo</Badge>
                <span className="text-xs text-ink-2">
                  {s.stop.since ? `desde ${dateTime(s.stop.since)}` : "job e coletores parados"}
                  {s.stop.source ? ` · ${s.stop.source}` : ""}
                </span>
              </>
            ) : (
              <>
                <Badge tone="ok">Inativo</Badge>
                <span className="text-xs text-ink-2">job e coletores liberados</span>
              </>
            )
          ) : (
            <>
              <Badge tone="neutral">Desconhecido</Badge>
              <span className="text-xs text-ink-2" title={status.unavailable?.message}>
                {status.unavailable?.status === 404
                  ? "a API não expõe /v1/status"
                  : `não foi possível consultar /v1/status: ${status.unavailable ? fallbackReason(status.unavailable) : "sem resposta"}`}
              </span>
            </>
          )}
        </dd>
      </div>
      <div className="min-w-0">
        <dt className="text-xs text-ink-3">Último job diário</dt>
        <dd className="mt-1 text-ink">
          {runAt ? (
            <>
              {relativeFrom(runAt, now)} <span className="text-xs text-ink-3">· {dateTime(runAt)}</span>
              <span className="block text-xs text-ink-2">dados de {timeUTC(runAt)}</span>
              {s?.last_job?.status && s.last_job.status !== "ok" ? (
                <span className="ml-2 text-xs font-medium text-crit">{s.last_job.status}</span>
              ) : null}
            </>
          ) : (
            "—"
          )}
        </dd>
      </div>
      <div className="min-w-0">
        <dt className="text-xs text-ink-3">Base histórica</dt>
        <dd className="mt-1 text-ink">
          {s?.n_campaigns_total !== null && s?.n_campaigns_total !== undefined ? (
            <>
              Baseado em <span className="tnum font-semibold">{int(s.n_campaigns_total)}</span> campanhas históricas
            </>
          ) : (
            <span className="text-ink-2">Baseado em campanhas históricas por par; o número está na explicação de cada item</span>
          )}
        </dd>
      </div>
    </dl>
  );
}
