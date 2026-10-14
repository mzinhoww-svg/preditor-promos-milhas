import type { Metadata } from "next";
import Link from "next/link";
import { Badge, SEVERITY_TONE } from "@/components/badge";
import { DataNotice } from "@/components/data-notice";
import { Freshness } from "@/components/freshness";
import { PageHeader, Section, SummaryPanel } from "@/components/page-header";
import { ScrollRegion } from "@/components/scroll-region";
import { StatusStrip } from "@/components/status-strip";
import { dataSource, getAccuracy, getSourceHealth, getStatus, getThresholdAlerts, type Alert, type AlertSeverity } from "@/lib/api";
import { ALERT_KIND_LABEL, OFFER_TYPE_SHORT, SEVERITY_LABEL, SOURCE_STATUS_LABEL, dateTime, pct, relativeFrom } from "@/lib/format";

export const metadata: Metadata = { title: "Alertas" };
export const dynamic = "force-dynamic";

const ORDER: AlertSeverity[] = ["critical", "warning", "info"];

/** Alertas da API mais os derivados de fontes fora de "ok" que ainda não têm alerta próprio. */
function mergeAlerts(fromApi: Alert[], sources: Awaited<ReturnType<typeof getSourceHealth>>["data"]["sources"]): Alert[] {
  const covered = new Set(fromApi.map((a) => a.related.source).filter(Boolean));
  const derived: Alert[] = sources
    .filter((s) => s.status !== "ok" && !covered.has(s.source))
    .map((s) => ({
      id: `src_${s.source}`,
      severity: s.status === "blocked" || s.status === "error" ? "critical" : s.status === "degraded" ? "warning" : "info",
      kind: "source",
      title: `${s.source}: ${SOURCE_STATUS_LABEL[s.status].toLowerCase()}`,
      detail: s.message ?? "Fonte fora do estado normal; ver detalhes na tela de fontes.",
      since: s.last_success_at ?? s.last_item_at ?? "",
      related: { horizon: null, source: s.source, pair: null },
    }));
  return [...fromApi, ...derived].sort(
    (a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity) || b.since.localeCompare(a.since),
  );
}

export default async function AlertsPage() {
  const configured = dataSource();
  const [accRes, shRes, thrRes, statusRes] = await Promise.all([getAccuracy(), getSourceHealth(), getThresholdAlerts(), getStatus()]);
  const acc = accRes.data;
  const sh = shRes.data;
  const discarded = accRes.discarded;
  const now = new Date();
  const stopActive = statusRes.data?.stop.active ?? false;
  const stopAlert: Alert[] = stopActive
    ? [
        {
          id: "stop",
          severity: "critical",
          kind: "pipeline",
          title: "Parada de emergência (STOP) ativa",
          detail: "Job diário e coletores abortam antes de ler ou gravar. As predições abaixo não são atualizadas até o STOP ser removido.",
          since: statusRes.data?.stop.since ?? statusRes.data?.generated_at ?? acc.generated_at,
          related: { horizon: null, source: null, pair: null },
        },
      ]
    : [];
  const alerts = mergeAlerts([...stopAlert, ...acc.alerts], sh.sources);
  const thr = thrRes.data;
  const count = (s: AlertSeverity) => alerts.filter((a) => a.severity === s).length;

  return (
    <>
      <PageHeader
        title="Alertas"
        description="Drift do modelo, fontes com problema, orçamento, pipeline e cruzamentos de limiar de probabilidade. Ordenados por gravidade e depois pelos mais recentes."
      />

      <DataNotice configured={configured} sources={[accRes, shRes]} />

      <SummaryPanel
        items={[
          { label: "Críticos", value: count("critical") },
          { label: "Atenção", value: count("warning") },
          { label: "Informativos", value: count("info") },
          { label: "Cruzaram o limiar", value: thr ? thr.items.length : "—", hint: thr ? `limiar ${thr.items[0] ? pct(thr.items[0].threshold) : "—"}` : "rota indisponível" },
        ]}
      />

      <Freshness origin={accRes.origin} fetchedAt={accRes.fetchedAt} generatedAt={acc.generated_at} now={now} />

      <StatusStrip status={statusRes} jobFallbackAt={acc.generated_at} now={now} />

      {discarded > 0 ? (
        <p role="status" className="mb-4 rounded-md border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
          {discarded === 1 ? "1 alerta da API foi descartado" : `${discarded} alertas da API foram descartados`} por
          formato inválido.
        </p>
      ) : null}

      <Section title="Operação e fontes" description={`${alerts.length} alertas ativos.`}>
        {alerts.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line-strong px-4 py-10 text-center text-sm text-ink-2">
            Nenhum alerta ativo. O job diário e as fontes estão dentro do esperado.
          </p>
        ) : (
          <ol className="divide-y divide-line">
            {alerts.map((a, i) => (
              <li key={`${i}-${a.id}`} className="grid min-w-0 gap-x-6 gap-y-2 py-4 sm:grid-cols-[7rem_minmax(0,1fr)_10rem]">
                <div className="flex items-start gap-2 sm:flex-col sm:gap-1">
                  <Badge tone={SEVERITY_TONE[a.severity]}>{SEVERITY_LABEL[a.severity]}</Badge>
                  <span className="text-xs text-ink-3">{ALERT_KIND_LABEL[a.kind]}</span>
                </div>
                <div className="min-w-0">
                  <h3 className="break-words text-sm font-semibold text-ink">{a.title}</h3>
                  <p className="mt-1 max-w-prose break-words text-sm leading-6 text-ink-2">{a.detail}</p>
                  {a.related.source || a.related.horizon || a.related.pair ? (
                    <p className="mt-1.5 break-all text-xs text-ink-3">
                      {a.related.source ? (
                        <>
                          Fonte:{" "}
                          <Link href="/fontes" className="font-medium text-primary underline underline-offset-2">
                            {a.related.source}
                          </Link>
                        </>
                      ) : null}
                      {a.related.horizon ? (
                        <>
                          {a.related.source ? " · " : ""}Horizonte:{" "}
                          <Link href="/modelo" className="font-medium text-primary underline underline-offset-2">
                            {a.related.horizon} dias
                          </Link>
                        </>
                      ) : null}
                      {a.related.pair ? ` · Par: ${a.related.pair}` : null}
                    </p>
                  ) : null}
                </div>
                <div className="text-xs text-ink-3 sm:text-right">
                  <div className="text-ink-2">{a.since ? relativeFrom(a.since, now) : "—"}</div>
                  <div>{a.since ? dateTime(a.since) : ""}</div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section
        title="Cruzaram o limiar de probabilidade"
        description="Registrados pelo job diário quando a probabilidade de um par e janela passa do limiar configurado. Sem canal externo: ficam só aqui."
      >
        {!thr ? (
          <p className="rounded-lg border border-dashed border-line-strong px-4 py-8 text-center text-sm text-ink-2" title={thrRes.unavailable?.message}>
            A API ainda não expõe <code className="font-mono text-xs">/v1/alerts</code>
            {thrRes.unavailable?.status ? ` (HTTP ${thrRes.unavailable.status})` : ""}. Entra com a T10b.
          </p>
        ) : thr.items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line-strong px-4 py-8 text-center text-sm text-ink-2">
            Nenhum par cruzou o limiar nas últimas execuções.
          </p>
        ) : (
          <>
            {thrRes.discarded > 0 ? (
              <p role="status" className="mb-3 rounded-md border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
                {thrRes.discarded === 1 ? "1 registro da API foi descartado" : `${thrRes.discarded} registros da API foram descartados`} por formato inválido.
              </p>
            ) : null}
            <ScrollRegion label="Tabela de cruzamentos de limiar">
              <table className="w-full min-w-[40rem] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs font-medium text-ink-3">
                    <th className="py-2 pr-4 font-medium">Par</th>
                    <th className="py-2 pr-4 font-medium">Tipo</th>
                    <th className="tnum py-2 pr-4 text-right font-medium">Janela</th>
                    <th className="tnum py-2 pr-4 text-right font-medium">Probabilidade</th>
                    <th className="tnum py-2 pr-4 text-right font-medium">Anterior</th>
                    <th className="tnum py-2 pr-4 text-right font-medium">Limiar</th>
                    <th className="py-2 font-medium">Quando</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {thr.items.map((t, i) => (
                    <tr key={`${i}-${t.made_at}-${t.pair.origin}-${t.pair.destination}-${t.horizon_days}`}>
                      <td className="py-2.5 pr-4 font-medium text-ink">
                        {t.pair.origin}
                        <span aria-hidden="true" className="mx-1 text-ink-3">
                          &rarr;
                        </span>
                        <span className="sr-only"> para </span>
                        {t.pair.destination}
                      </td>
                      <td className="py-2.5 pr-4 text-ink-2">{OFFER_TYPE_SHORT[t.type]}</td>
                      <td className="tnum py-2.5 pr-4 text-right text-ink-2">{t.horizon_days} d</td>
                      <td className="tnum py-2.5 pr-4 text-right font-semibold text-ink">{pct(t.probability)}</td>
                      <td className="tnum py-2.5 pr-4 text-right text-ink-2">{t.previous_probability === null ? "—" : pct(t.previous_probability)}</td>
                      <td className="tnum py-2.5 pr-4 text-right text-ink-2">{pct(t.threshold)}</td>
                      <td className="py-2.5 text-ink-2">
                        {relativeFrom(t.made_at, now)} <span className="text-xs text-ink-3">· {dateTime(t.made_at)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          </>
        )}
      </Section>
    </>
  );
}
