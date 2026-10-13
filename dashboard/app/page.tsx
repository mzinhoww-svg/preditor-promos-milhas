import Link from "next/link";
import type { Metadata } from "next";
import { PageHeader, SummaryPanel } from "@/components/page-header";
import { PredictionList } from "@/components/prediction-list";
import { getPredictions, type OfferType } from "@/lib/api";
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

  const [all, data] = await Promise.all([getPredictions(), getPredictions({ type })]);

  const top = all.items[0];
  const likely30 = all.items.filter((i) => i.windows["30"].probability >= 0.5).length;
  const likely7 = all.items.filter((i) => i.windows["7"].probability >= 0.5).length;

  return (
    <>
      <PageHeader
        title="Próximas promoções prováveis"
        description="Lista ranqueada por probabilidade de uma nova oferta começar nos próximos 30 dias. Cada item traz a probabilidade calibrada por janela, a faixa prevista do bônus e os fatores que o colocaram ali."
      />

      <SummaryPanel
        items={[
          {
            label: "Mais provável em 7 dias",
            value: top ? `${top.pair.origin} → ${top.pair.destination}` : "—",
            hint: top ? `${pct(top.windows["7"].probability)} · mediana ${top.bonus_pct.p50}%` : undefined,
          },
          { label: "Pares com ≥ 50% em 7 dias", value: likely7, hint: `de ${all.items.length} acompanhados` },
          { label: "Pares com ≥ 50% em 30 dias", value: likely30, hint: `de ${all.items.length} acompanhados` },
          {
            label: "Modelo em produção",
            value: `${all.model.name} ${all.model.version}`,
            hint: `gerado ${dateTime(all.generated_at)}`,
          },
        ]}
      />

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

      <PredictionList items={data.items} />

      <p className="mt-6 max-w-prose text-xs leading-5 text-ink-3">
        Probabilidade é a chance calibrada de uma oferta do par e tipo começar dentro da janela, contada a partir de{" "}
        {dateTime(all.generated_at)}. O intervalo abaixo da barra vem de bootstrap em blocos. P25, P50 e P75 são
        os quartis do bônus previsto em pontos percentuais. Ofertas segmentadas (clube, cartão) têm linha própria e
        não se misturam com a oferta geral.
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
