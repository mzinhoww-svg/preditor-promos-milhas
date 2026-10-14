"use client";

import Link from "next/link";
import { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";
import type { DataSource } from "@/lib/api/source";

const LINKS = [
  { href: "/", label: "Previsões" },
  { href: "/modelo", label: "Modelo" },
  { href: "/fontes", label: "Fontes" },
  { href: "/alertas", label: "Alertas" },
] as const;

export function Nav({ source }: { source: DataSource }) {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-bg/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl flex-col px-4 sm:flex-row sm:items-center sm:gap-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 py-3 sm:flex-nowrap sm:py-0">
          <Link href="/" className="flex shrink-0 items-center gap-2 text-sm font-semibold tracking-tight text-ink">
            <span aria-hidden="true" className="inline-block size-2.5 rounded-sm bg-primary" />
            Preditor de promoções
          </Link>
          <SourceBadge source={source} className="sm:hidden" />
        </div>
        <nav aria-label="Principal" className="-mx-1 -mb-px flex items-stretch gap-1 overflow-x-auto sm:mx-0 sm:flex-1">
          {LINKS.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={
                  "flex items-center whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition-colors duration-150 sm:py-3 " +
                  (active
                    ? "border-primary font-medium text-ink"
                    : "border-transparent text-ink-2 hover:border-line-strong hover:text-ink")
                }
              >
                {l.label}
                <PendingDot />
              </Link>
            );
          })}
        </nav>
        <SourceBadge source={source} className="hidden sm:inline-block" />
      </div>
    </header>
  );
}

/**
 * Estado de carregamento da navegação: a tela de destino é renderizada no
 * servidor, então o link mostra um ponto pulsante enquanto a resposta não chega.
 */
function PendingDot() {
  const { pending } = useLinkStatus();
  if (!pending) return null;
  return (
    <span role="status" className="ml-1.5 inline-flex items-center">
      <span className="sr-only">Carregando</span>
      <span aria-hidden="true" className="inline-block size-1.5 animate-pulse rounded-full bg-primary motion-reduce:animate-none" />
    </span>
  );
}

function SourceBadge({ source, className }: { source: DataSource; className?: string }) {
  const mock = source === "mock";
  return (
    <span
      className={
        "max-w-full truncate rounded-full border px-2 py-0.5 text-xs font-medium sm:shrink-0 " +
        (mock ? "border-warn/40 bg-warn-soft text-warn " : "border-ok/40 bg-ok-soft text-ok ") +
        (className ?? "")
      }
      title={mock ? "Nenhuma API configurada: dados de exemplo de dashboard/mock" : "Lendo a API do preditor (com fallback para dados simulados se ela falhar)"}
    >
      {mock ? "Dados simulados" : "API"}
    </span>
  );
}
