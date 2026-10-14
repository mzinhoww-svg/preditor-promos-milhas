import Link from "next/link";
import { Badge } from "@/components/badge";
import { ExplanationPanel } from "@/components/explanation";
import { MethodBadge } from "@/components/model-badge";
import { Probability } from "@/components/probability";
import { HORIZONS, type PredictionItem, type Reason } from "@/lib/api/types";
import { OFFER_TYPE_LABEL, OFFER_TYPE_SHORT, dateShort, pct } from "@/lib/format";

function PairName({ item }: { item: PredictionItem }) {
  const same = item.pair.origin === item.pair.destination;
  return (
    <span className="min-w-0 break-words text-base font-semibold tracking-tight text-ink">
      {item.pair.origin}
      {same ? null : (
        <>
          <span aria-hidden="true" className="mx-1.5 text-ink-3">
            &rarr;
          </span>
          <span className="sr-only"> para </span>
          {item.pair.destination}
        </>
      )}
    </span>
  );
}

const REASON_KIND_LABEL: Record<Reason["kind"], string> = {
  days_since_last: "Intervalo",
  month: "Sazonalidade",
  sibling_pairs: "Pares irmãos",
  source_signal: "Sinal de fonte",
  other: "Outro",
};

function Reasons({ reasons }: { reasons: Reason[] }) {
  if (reasons.length === 0) return null;
  return (
    <ul className="mt-3 flex flex-col gap-1.5 border-t border-line pt-3" aria-label="Fatores ponderados">
      {reasons.map((r, i) => (
        <li key={`${i}-${r.kind}`} className="flex items-start gap-2 text-sm leading-5">
          <span className="tnum mt-0.5 w-9 shrink-0 text-right text-xs text-ink-3" title="peso do fator">
            {pct(Math.max(0, Math.min(1, r.weight)))}
          </span>
          <span className="min-w-0 break-words">
            <span className="text-ink">{r.label}</span>
            {r.detail ? <span className="text-ink-3"> · {r.detail}</span> : null}
            <span className="sr-only"> ({REASON_KIND_LABEL[r.kind]})</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function Bonus({ v, big = false }: { v: number | null; big?: boolean }) {
  const cls = big ? "tnum text-xl font-semibold tracking-tight text-ink" : "tnum text-sm text-ink-2";
  return <span className={cls}>{v === null ? "—" : `${v}%`}</span>;
}

export function PredictionList({ items }: { items: PredictionItem[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-line-strong px-6 py-12 text-center">
        <p className="text-sm font-medium text-ink">Nenhuma previsão para esse filtro.</p>
        <p className="mt-1 text-sm text-ink-2">
          Volte para{" "}
          <Link href="/" className="font-medium text-primary underline underline-offset-2">
            todos os tipos
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Cabeçalho só no desktop; no celular cada item carrega os rótulos. */}
      <div className="hidden grid-cols-[2.5rem_minmax(0,1.6fr)_repeat(3,minmax(0,0.9fr))_minmax(0,1.1fr)] gap-x-4 border-b border-line pb-2 text-xs font-medium text-ink-3 lg:grid">
        <div>#</div>
        <div>Par e tipo</div>
        <div>7 dias</div>
        <div>15 dias</div>
        <div>30 dias</div>
        <div>Bônus previsto (P25 · P50 · P75)</div>
      </div>

      <ol className="divide-y divide-line">
        {items.map((item, index) => {
          const hint = item.reasons[0]?.label ?? (item.n_campaigns !== null ? `baseado em ${item.n_campaigns} campanhas históricas` : null);
          const hasBonus = item.bonus_pct.p25 !== null || item.bonus_pct.p50 !== null || item.bonus_pct.p75 !== null;
          return (
            <li key={`${index}-${item.rank}-${item.pair.origin}-${item.pair.destination}-${item.type}`}>
              <article className="grid min-w-0 grid-cols-1 gap-x-4 gap-y-4 py-5 lg:grid-cols-[2.5rem_minmax(0,1.6fr)_repeat(3,minmax(0,0.9fr))_minmax(0,1.1fr)]">
                <div className="tnum hidden text-lg font-semibold text-ink-3 lg:block">{item.rank}</div>

                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="tnum text-sm font-semibold text-ink-3 lg:hidden">{item.rank}.</span>
                    <PairName item={item} />
                  </div>
                  <div className="mt-1.5 flex min-w-0 flex-wrap items-center gap-1.5">
                    <Badge tone="primary">{OFFER_TYPE_SHORT[item.type]}</Badge>
                    {item.method ? <MethodBadge method={item.method} /> : null}
                    {item.segmented && item.segment_label ? (
                      <Badge title={item.segment_label}>{item.segment_label}</Badge>
                    ) : null}
                    <span className="sr-only">{OFFER_TYPE_LABEL[item.type]}</span>
                  </div>
                  {item.last_offer ? (
                    <p className="mt-2 text-xs leading-5 text-ink-2">
                      Última oferta: {dateShort(item.last_offer.start_at)}
                      {item.last_offer.end_at ? `–${dateShort(item.last_offer.end_at)}` : " (em curso)"} com{" "}
                      <span className="tnum">{item.last_offer.bonus_pct}%</span>
                      {" · "}
                      <span className="tnum">{item.last_offer.days_since}</span> dias atrás
                    </p>
                  ) : (
                    <p className="mt-2 text-xs leading-5 text-ink-3">Última campanha e recência em “Por que está na lista”.</p>
                  )}
                </div>

                <div className="grid grid-cols-[repeat(auto-fit,minmax(5.5rem,1fr))] gap-3 lg:contents">
                  {HORIZONS.map((h, i) => (
                    <div key={h}>
                      <div className="mb-1 text-xs text-ink-3 lg:hidden">{h} dias</div>
                      <Probability w={item.windows[h]} emphasis={i === 2} />
                    </div>
                  ))}
                </div>

                <div>
                  <div className="mb-1 text-xs text-ink-3 lg:hidden">Bônus previsto (P25 · P50 · P75)</div>
                  {hasBonus ? (
                    <>
                      <div className="flex items-baseline gap-1.5">
                        <Bonus v={item.bonus_pct.p25} />
                        <span aria-hidden="true" className="text-ink-3">
                          ·
                        </span>
                        <Bonus v={item.bonus_pct.p50} big />
                        <span aria-hidden="true" className="text-ink-3">
                          ·
                        </span>
                        <Bonus v={item.bonus_pct.p75} />
                      </div>
                      <p className="mt-1 text-xs text-ink-3">mediana e quartis do bônus</p>
                    </>
                  ) : (
                    <p className="text-sm text-ink-2">Sem histórico de bônus para o par.</p>
                  )}
                </div>

                <div className="min-w-0 lg:col-span-6 lg:pl-[3.5rem]">
                  <ExplanationPanel origin={item.pair.origin} destination={item.pair.destination} type={item.type} summaryHint={hint}>
                    <Reasons reasons={item.reasons} />
                  </ExplanationPanel>
                </div>
              </article>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
