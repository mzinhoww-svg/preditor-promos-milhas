import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  aside,
}: {
  title: string;
  description?: string;
  aside?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 max-w-2xl">
        <h1 className="break-words text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description ? <p className="mt-1 text-sm leading-6 text-ink-2">{description}</p> : null}
      </div>
      {aside ? <div className="shrink-0">{aside}</div> : null}
    </div>
  );
}

/** Painel escuro: um por tela, para o resumo que ancora a leitura. */
export function SummaryPanel({
  items,
  children,
}: {
  items: { label: string; value: ReactNode; hint?: string }[];
  children?: ReactNode;
}) {
  return (
    <section
      aria-label="Resumo"
      className="mb-8 min-w-0 rounded-lg bg-panel px-5 py-5 text-panel-ink sm:px-6"
    >
      <dl className="grid grid-cols-[repeat(auto-fit,minmax(8rem,1fr))] gap-x-6 gap-y-5">
        {items.map((it, i) => (
          <div key={`${i}-${it.label}`} className="min-w-0">
            <dt className="break-words text-xs text-panel-ink-2">{it.label}</dt>
            <dd
              className="tnum mt-1 min-w-0 break-words text-xl font-semibold leading-tight tracking-tight sm:text-2xl"
              title={typeof it.value === "string" ? it.value : undefined}
            >
              {it.value}
            </dd>
            {it.hint ? (
              <dd className="mt-1 truncate text-xs text-panel-ink-2" title={it.hint}>
                {it.hint}
              </dd>
            ) : null}
          </div>
        ))}
      </dl>
      {children}
    </section>
  );
}

export function Section({
  title,
  description,
  children,
  aside,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <section className="mb-10 min-w-0">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          {description ? <p className="mt-0.5 max-w-prose text-sm text-ink-2">{description}</p> : null}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}
