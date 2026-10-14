import Link from "next/link";
import type { Metadata } from "next";
import { DataNotice } from "@/components/data-notice";
import { Freshness } from "@/components/freshness";
import { HeaderModelBadge } from "@/components/model-badge";
import { PageHeader, SummaryPanel } from "@/components/page-header";
import { PredictionList } from "@/components/prediction-list";
import { StatusStrip } from "@/components/status-strip";
import { dataSource, getExplanations, getModelMetrics, getPredictions, getStatus, withExplanations, type OfferType } from "@/lib/api";
import { probabilityWord } from "@/lib/model-label";
import { OFFER_TYPE_LABEL, dateTime, pct } from "@/lib/format";

export const metadata: Metadata = { title: "Previsões" };
export const dynamic = "force-dynamic";

const TYPES: OfferType[] = ["transfer_bonus", "purchase_discount", "boosted_accrual"];

function isOfferType(v: string | undefined): v is OfferType {
  return !!v && (TYPES as string[]).includes(v);
}

export default async function PredictionsPage({ searchParams }: PageProps<"/">) {
  const sp = await searchParams;
  const rawType = Array.isArray(sp.type) ? sp.type[0] : sp.type;
  const type = isOfferType(rawType) ? rawType : undefined;

  const configured = dataSource();
  const [predRes, metricsRes, statusRes] = await Promise.all([getPredictions(), getModelMetrics(), getStatus()]);
  // Método por par vem da explicação (a lista ainda não o traz): até 12 itens, memorizado por 5 min.
  const expl = await getExplanations(predRes.data.items);
  const all = { ...predRes.data, items: withExplanations(predRes.data.items, expl.byKey) };
  const items = type ? all.items.filter((i) => i.type === type) : all.items;
  const word = probabilityWord(metricsRes.origin === "api" || configured === "mock" ? metricsRes.data : null);
  const discarded = predRes.discarded;
  const invalidWindows = predRes.invalidWindows;
  const now = new Date();
  const decision = metricsRes.origin === "api" || configured === "mock" ? metricsRes.data.comparison.decision : null;

  const top = all.items[0];
  const likely30 = all.items.filter((i) => (i.windows["30"]?.probability ?? 0) >= 0.5).length;
  const likely7 = all.items.filter((i) => (i.windows["7"]?.probability ?? 0) >= 0.5).length;

  return (
    <>
      <PageHeader
        title="Próximas promoções prováveis"
        description={`Lista ranqueada por probabilidade de uma nova oferta começar nos próximos 30 dias. Cada item traz a probabilidade ${word} por janela, os bônus das campanhas anteriores e o contexto histórico do par.`}
      />

      <DataNotice configured={configured} sources={[predRes, metricsRes]} />

      <SummaryPanel
        items={[
          {
            label: "Mais provável em 7 dias",
            value: top ? `${top.pair.origin} → ${top.pair.destination}` : "—",
            hint: top ? `${top.windows["7"] ? pct(top.windows["7"].probability) : "janela de 7 d inválida"}${top.bonus_pct.p50 !== null ? ` · mediana histórica ${top.bonus_pct.p50}%` : ""}` : undefined,
          },
          { label: "Pares com ≥ 50% em 7 dias", value: likely7, hint: `de ${all.items.length} acompanhados` },
          { label: "Pares com ≥ 50% em 30 dias", value: likely30, hint: `de ${all.items.length} acompanhados` },
          {
            label: "Modelo em produção",
            value: <HeaderModelBadge name={all.model.name} items={all.items} decision={decision} />,
            hint: `execução ${all.model.run_id} · gerado ${dateTime(all.generated_at)}`,
          },
        ]}
      />

      <Freshness origin={predRes.origin} fetchedAt={predRes.fetchedAt} generatedAt={all.generated_at} now={now} />

      <StatusStrip status={statusRes} jobFallbackAt={all.generated_at} now={now} />

      <nav aria-label="Filtrar por tipo" className="mb-4 flex flex-wrap gap-2">
        <FilterChip href="/" active={!type}>
          Todos os tipos
        </FilterChip>
        {TYPES.map((t) => (
          <FilterChip key={t} href={`/?type=${t}`} active={type === t}>
            {OFFER_TYPE_LABEL[t]}
          </FilterChip>
        ))}
      </nav>

      {discarded > 0 ? (
        <p role="status" className="mb-4 rounded-md border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
          {discarded === 1 ? "1 item da API foi descartado" : `${discarded} itens da API foram descartados`} por formato
          inválido. A lista abaixo mostra só os itens válidos.
        </p>
      ) : null}

      {invalidWindows > 0 ? (
        <p role="status" className="mb-4 rounded-md border border-crit/30 bg-crit-soft px-3 py-2 text-sm text-crit">
          {invalidWindows === 1 ? "1 janela veio inválida da API" : `${invalidWindows} janelas vieram inválidas da API`} e
          está marcada no item, sem tirar o par da lista.
        </p>
      ) : null}

      <PredictionList items={items} />

      <p className="mt-6 max-w-prose text-xs leading-5 text-ink-3">
        Probabilidade é a chance {word} de uma oferta do par e tipo começar dentro da janela, contada a partir de{" "}
        {dateTime(all.generated_at)}. O intervalo abaixo da barra, quando existe, vem de bootstrap em blocos. P25, P50 e
        P75 são os quartis dos bônus nas campanhas anteriores do par, em pontos percentuais; não são uma previsão do próximo
        bônus. Pares com menos de 25 campanhas usam a taxa-base (B0);
        com 25 ou mais, o hazard empírico (B1). Ofertas segmentadas (clube, cartão) têm linha própria.
      </p>
    </>
  );
}

function FilterChip({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      aria-current={active ? "true" : undefined}
      className={
        "rounded-full border px-3 py-1 text-sm transition-colors duration-150 " +
        (active
          ? "border-ink bg-ink text-bg"
          : "border-line text-ink-2 hover:border-line-strong hover:text-ink")
      }
    >
      {children}
    </Link>
  );
}
