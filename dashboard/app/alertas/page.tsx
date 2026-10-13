import type { Metadata } from "next";
import Link from "next/link";
import { Badge, SEVERITY_TONE } from "@/components/badge";
import { PageHeader, Section, SummaryPanel } from "@/components/page-header";
import { getAccuracy, getSourceHealth, type Alert, type AlertSeverity } from "@/lib/api";
import { ALERT_KIND_LABEL, SEVERITY_LABEL, SOURCE_STATUS_LABEL, dateTime, relativeFrom } from "@/lib/format";

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
  const [accRes, shRes] = await Promise.all([getAccuracy(), getSourceHealth()]);
  const acc = accRes.data;
  const sh = shRes.data;
  const discarded = accRes.discarded;
  const now = new Date(acc.generated_at);
  const alerts = mergeAlerts(acc.alerts, sh.sources);
  const count = (s: AlertSeverity) => alerts.filter((a) => a.severity === s).length;

  return (
    <>
      <PageHeader
        title="Alertas"
        description="Drift do modelo, fontes com problema, orçamento e pipeline. Ordenados por gravidade e depois pelos mais recentes."
      />

      <SummaryPanel
        items={[
          { label: "Críticos", value: count("critical") },
          { label: "Atenção", value: count("warning") },
          { label: "Informativos", value: count("info") },
          { label: "Atualizado", value: dateTime(acc.generated_at) },
        ]}
      />

      {discarded > 0 ? (
        <p role="status" className="mb-4 rounded-md border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
          {discarded === 1 ? "1 alerta da API foi descartado" : `${discarded} alertas da API foram descartados`} por
          formato inválido.
        </p>
      ) : null}

      <Section title="Lista" description={`${alerts.length} alertas ativos.`}>
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
    </>
  );
}
