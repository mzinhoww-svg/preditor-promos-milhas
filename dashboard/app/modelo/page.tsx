import type { Metadata } from "next";
import { Badge } from "@/components/badge";
import { PageHeader, Section, SummaryPanel } from "@/components/page-header";
import { ReliabilityChart } from "@/components/reliability-chart";
import { ScrollRegion } from "@/components/scroll-region";
import { getAccuracy, getModelMetrics, HORIZONS, type ModelSummary } from "@/lib/api";
import { dateLong, dateTime, int, num, pct, signed } from "@/lib/format";

export const metadata: Metadata = { title: "Modelo" };
export const dynamic = "force-dynamic";

const DECISION_LABEL = {
  keep_champion: "Campeão mantido",
  promote_challenger: "Promover desafiante",
  insufficient_data: "Dados insuficientes",
} as const;

export default async function ModelPage() {
  const [m, accRes] = await Promise.all([getModelMetrics(), getAccuracy()]);
  const acc = accRes.data;
  const discardedWeekly = accRes.discardedWeekly;
  const c = m.champion;
  const prod = c.production;

  return (
    <>
      <PageHeader
        title="Métricas do modelo"
        description="Validação histórica (walk-forward) e precisão real em produção ficam lado a lado, mas nunca misturadas. A produção conta só predições registradas em prediction_log e já resolvidas."
      />

      <SummaryPanel
        items={[
          { label: "Em produção", value: `${c.name} ${c.version}`, hint: `treinado ${dateLong(c.trained_at)}` },
          {
            label: "Brier em produção · 30 d",
            value: prod ? num(prod.by_horizon["30"].brier) : "—",
            hint: prod ? `validação: ${num(c.validation.by_horizon["30"].brier)}` : "sem predições resolvidas",
          },
          {
            label: "Acerto em produção · 30 d",
            value: prod ? pct(prod.by_horizon["30"].hit_rate) : "—",
            hint: prod ? `${int(prod.n_resolved)} de ${int(prod.n_predictions)} resolvidas` : undefined,
          },
          {
            label: "Campeão × desafiante",
            value: DECISION_LABEL[m.comparison.decision],
            hint: `Δ Brier ${signed(m.comparison.delta_brier)}${m.comparison.ci_delta_brier ? ` · IC ${num(m.comparison.ci_delta_brier[0])} a ${num(m.comparison.ci_delta_brier[1])}` : " · IC indisponível"}`,
          },
        ]}
      />

      <div className="grid min-w-0 gap-x-10 gap-y-10 lg:grid-cols-2">
        <Section
          title="Validação histórica"
          description={`${c.validation.method}, ${c.validation.folds === null ? "número de dobras não informado" : `${c.validation.folds} dobras`}, ${dateLong(c.validation.period.from)} a ${dateLong(c.validation.period.to)}. Mede o que o modelo teria acertado no passado.`}
        >
          <MetricTable
            label="Tabela de validação histórica por janela"
            rows={HORIZONS.map((h) => {
              const v = c.validation.by_horizon[h];
              return {
                horizon: h,
                cells: [num(v.brier), v.ci_brier ? `${num(v.ci_brier[0])}–${num(v.ci_brier[1])}` : "—", num(v.log_loss), num(v.auc, 2)],
              };
            })}
            headers={["Brier", "IC Brier", "Log-loss", "AUC"]}
          />
        </Section>

        <Section
          title="Precisão real em produção"
          description={
            prod
              ? `${dateLong(prod.period.from)} a ${dateLong(prod.period.to)}. Predições servidas pelo painel, conferidas com o que aconteceu.`
              : "Ainda sem predições resolvidas em produção."
          }
        >
          {prod ? (
            <MetricTable
              label="Tabela de precisão em produção por janela"
              rows={HORIZONS.map((h) => {
                const p = prod.by_horizon[h];
                const v = c.validation.by_horizon[h];
                const delta = p.brier - v.brier;
                return {
                  horizon: h,
                  cells: [num(p.brier), signed(delta), num(p.log_loss), pct(p.hit_rate), int(p.n)],
                  flag: v.ci_brier ? delta > v.ci_brier[1] - v.brier : false,
                };
              })}
              headers={["Brier", "Δ vs. validação", "Log-loss", "Acerto", "n"]}
            />
          ) : (
            <p className="rounded-lg border border-dashed border-line-strong px-4 py-8 text-center text-sm text-ink-2">
              Quando o job diário registrar predições e elas vencerem, esta tabela se preenche sozinha.
            </p>
          )}
          <p className="mt-2 text-xs text-ink-3">
            Δ positivo = pior que a validação. Linhas marcadas estão fora do intervalo de confiança da validação.
          </p>
        </Section>

        <Section
          title={`Curva de confiabilidade · ${m.reliability.horizon} dias`}
          description="Quando o modelo diz 70%, acontece em cerca de 70% das vezes? Pontos na diagonal dizem que sim."
        >
          <ReliabilityChart bins={m.reliability.bins} horizon={m.reliability.horizon} />
        </Section>

        <Section
          title="Campeão × desafiante"
          description="O desafiante só vai para produção se vencer em Brier e log-loss com intervalo de confiança por bootstrap em blocos."
        >
          <div className="grid min-w-0 gap-4 sm:grid-cols-2">
            <ModelCard model={c} role="Campeão" />
            {m.challenger ? (
              <ModelCard model={m.challenger} role="Desafiante" />
            ) : (
              <p className="text-sm text-ink-2">Sem desafiante treinado.</p>
            )}
          </div>
          <dl className="mt-4 grid grid-cols-[repeat(auto-fit,minmax(8rem,1fr))] gap-x-6 gap-y-3 rounded-lg border border-line p-4 text-sm">
            <div>
              <dt className="text-xs text-ink-3">Horizonte</dt>
              <dd className="tnum mt-0.5 font-medium text-ink">{m.comparison.horizon} dias</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-3">Δ Brier (desafiante − campeão)</dt>
              <dd className="tnum mt-0.5 font-medium text-ink">{signed(m.comparison.delta_brier)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-3">IC do Δ Brier</dt>
              <dd className="tnum mt-0.5 font-medium text-ink">
                {m.comparison.ci_delta_brier
                  ? `${num(m.comparison.ci_delta_brier[0])} a ${num(m.comparison.ci_delta_brier[1])}`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-3">Δ Log-loss</dt>
              <dd className="tnum mt-0.5 font-medium text-ink">{signed(m.comparison.delta_log_loss)}</dd>
            </div>
            <div className="col-span-full">
              <dt className="text-xs text-ink-3">Decisão</dt>
              <dd className="mt-0.5 flex flex-wrap items-center gap-2 text-ink">
                <Badge tone={m.comparison.decision === "promote_challenger" ? "ok" : "neutral"}>
                  {DECISION_LABEL[m.comparison.decision]}
                </Badge>
                <span className="min-w-0 break-words text-ink-2">{m.comparison.note}</span>
              </dd>
            </div>
          </dl>
        </Section>
      </div>

      <Section
        title="Acerto semanal em produção"
        description={`Horizonte de ${acc.weekly[0]?.horizon ?? 30} dias, por semana de emissão da predição.`}
      >
        {discardedWeekly > 0 ? (
          <p role="status" className="mb-3 rounded-md border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
            {discardedWeekly === 1 ? "1 semana da API foi descartada" : `${discardedWeekly} semanas da API foram descartadas`} por
            formato inválido.
          </p>
        ) : null}
        {acc.weekly.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line-strong px-4 py-8 text-center text-sm text-ink-2">
            Nenhuma semana com predições resolvidas no período.
          </p>
        ) : (
        <ScrollRegion label="Tabela de acerto semanal em produção">
          <table className="w-full min-w-[32rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs font-medium text-ink-3">
                <th className="py-2 pr-4 font-medium">Semana</th>
                <th className="py-2 pr-4 font-medium">n</th>
                <th className="py-2 pr-4 font-medium">Acerto</th>
                <th className="py-2 pr-4 font-medium">Brier</th>
                <th className="py-2 font-medium">Acerto (barra)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {acc.weekly.map((wk, i) => (
                <tr key={`${i}-${wk.week}`}>
                  <td className="py-2 pr-4 text-ink">{dateLong(wk.week)}</td>
                  <td className="tnum py-2 pr-4 text-ink-2">{int(wk.n)}</td>
                  <td className="tnum py-2 pr-4 font-medium text-ink">{pct(wk.hit_rate)}</td>
                  <td className="tnum py-2 pr-4 text-ink-2">{num(wk.brier)}</td>
                  <td className="py-2">
                    <div className="h-1.5 w-full max-w-[16rem] rounded-sm bg-primary-track" aria-hidden="true">
                      <div className="h-full rounded-sm bg-primary" style={{ width: `${Math.round(wk.hit_rate * 100)}%` }} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
        )}
      </Section>

      <p className="text-xs text-ink-3">Métricas geradas {dateTime(m.generated_at)}.</p>
    </>
  );
}

function MetricTable({
  label,
  headers,
  rows,
}: {
  label: string;
  headers: string[];
  rows: { horizon: string; cells: string[]; flag?: boolean }[];
}) {
  return (
    <ScrollRegion label={label}>
      <table className="w-full min-w-[26rem] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs font-medium text-ink-3">
            <th className="py-2 pr-4 font-medium">Janela</th>
            {headers.map((h) => (
              <th key={h} className="py-2 pr-4 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r, i) => (
            <tr key={`${i}-${r.horizon}`}>
              <td className="py-2.5 pr-4 font-medium text-ink">
                {r.horizon} dias
                {r.flag ? (
                  <Badge tone="warn">
                    <span className="ml-0">fora do IC</span>
                  </Badge>
                ) : null}
              </td>
              {r.cells.map((c, i) => (
                <td key={i} className={`tnum py-2.5 pr-4 ${i === 0 ? "font-medium text-ink" : "text-ink-2"}`}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollRegion>
  );
}

function ModelCard({ model, role }: { model: ModelSummary; role: string }) {
  const v30 = model.validation.by_horizon["30"];
  return (
    <div className="min-w-0 rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium text-ink-3">{role}</span>
        <Badge tone={model.production ? "ok" : "neutral"}>{model.production ? "em produção" : "sem produção"}</Badge>
      </div>
      <p className="mt-1 break-words text-lg font-semibold tracking-tight text-ink">
        {model.name} <span className="tnum text-base font-medium text-ink-2">{model.version}</span>
      </p>
      <dl className="mt-3 grid grid-cols-[repeat(auto-fit,minmax(4.5rem,1fr))] gap-2 text-sm">
        <div>
          <dt className="text-xs text-ink-3">Brier 30 d</dt>
          <dd className="tnum font-medium text-ink">{num(v30.brier)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3">Log-loss</dt>
          <dd className="tnum font-medium text-ink">{num(v30.log_loss)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3">AUC</dt>
          <dd className="tnum font-medium text-ink">{num(v30.auc, 2)}</dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-ink-3">Treinado {dateLong(model.trained_at)}</p>
    </div>
  );
}
