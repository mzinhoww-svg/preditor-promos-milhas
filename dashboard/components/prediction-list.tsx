import Link from "next/link";
import { Badge } from "@/components/badge";
import { Probability } from "@/components/probability";
import { HORIZONS, type PredictionItem, type Reason } from "@/lib/api/types";
import { OFFER_TYPE_LABEL, OFFER_TYPE_SHORT, dateShort } from "@/lib/format";

function PairName({ item }: { item: PredictionItem }) {
  const same = item.pair.origin === item.pair.destination;
  return (
    <span className="text-base font-semibold tracking-tight text-ink">
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
  return (
    <ul className="flex flex-col gap-1.5">
      {reasons.map((r) => (
        <li key={r.kind + r.label} className="flex items-start gap-2 text-sm leading-5">
          <span className="tnum mt-0.5 w-9 shrink-0 text-right text-xs text-ink-3" title="peso do fator">
            {Math.round(r.weight * 100)}%
          </span>
          <span className="min-w-0">
            <span className="text-ink">{r.label}</span>
            {r.detail ? <span className="text-ink-3"> · {r.detail}</span> : null}
            <span className="sr-only"> ({REASON_KIND_LABEL[r.kind]})</span>
          </span>
        </li>
      ))}
    </ul>
  );
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
        {items.map((item) => (
          <li key={`${item.rank}-${item.pair.origin}-${item.pair.destination}-${item.type}-${item.segment_label ?? ""}`}>
            <article className="grid grid-cols-1 gap-x-4 gap-y-4 py-5 lg:grid-cols-[2.5rem_minmax(0,1.6fr)_repeat(3,minmax(0,0.9fr))_minmax(0,1.1fr)]">
              <div className="tnum hidden text-lg font-semibold text-ink-3 lg:block">{item.rank}</div>

              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="tnum text-sm font-semibold text-ink-3 lg:hidden">{item.rank}.</span>
                  <PairName item={item} />
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <Badge tone="primary">{OFFER_TYPE_SHORT[item.type]}</Badge>
                  {item.segmented && item.segment_label ? <Badge>{item.segment_label}</Badge> : null}
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
                  <p className="mt-2 text-xs leading-5 text-ink-3">Sem oferta anterior conhecida</p>
                )}
              </div>

              <div className="grid grid-cols-3 gap-3 lg:contents">
                {HORIZONS.map((h, i) => (
                  <div key={h}>
                    <div className="mb-1 text-xs text-ink-3 lg:hidden">{h} dias</div>
                    <Probability w={item.windows[h]} emphasis={i === 2} />
                  </div>
                ))}
              </div>

              <div>
                <div className="mb-1 text-xs text-ink-3 lg:hidden">Bônus previsto (P25 · P50 · P75)</div>
                <div className="flex items-baseline gap-1.5">
                  <span className="tnum text-sm text-ink-2">{item.bonus_pct.p25}%</span>
                  <span aria-hidden="true" className="text-ink-3">
                    ·
                  </span>
                  <span className="tnum text-xl font-semibold tracking-tight text-ink">{item.bonus_pct.p50}%</span>
                  <span aria-hidden="true" className="text-ink-3">
                    ·
                  </span>
                  <span className="tnum text-sm text-ink-2">{item.bonus_pct.p75}%</span>
                </div>
                <p className="mt-1 text-xs text-ink-3">mediana e quartis do bônus</p>
              </div>

              <div className="lg:col-span-6 lg:pl-[3.5rem]">
                <details className="group rounded-md border border-line bg-surface-2 open:bg-bg">
                  <summary className="flex items-center justify-between gap-3 px-3 py-2 text-sm text-ink-2 hover:text-ink">
                    <span>
                      <span className="font-medium text-ink">Por que está na lista:</span>{" "}
                      {item.reasons[0]?.label}
                      {item.reasons.length > 1 ? ` e mais ${item.reasons.length - 1}` : ""}
                    </span>
                    <span aria-hidden="true" className="text-xs text-ink-3 group-open:hidden">
                      ver fatores
                    </span>
                    <span aria-hidden="true" className="hidden text-xs text-ink-3 group-open:inline">
                      ocultar
                    </span>
                  </summary>
                  <div className="border-t border-line px-3 py-3">
                    <Reasons reasons={item.reasons} />
                  </div>
                </details>
              </div>
            </article>
          </li>
        ))}
      </ol>
    </div>
  );
}
