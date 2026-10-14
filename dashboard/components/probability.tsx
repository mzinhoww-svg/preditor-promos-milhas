import { pct } from "@/lib/format";
import type { WindowProbability } from "@/lib/api/types";

/** Probabilidade com barra e intervalo. A barra é redundante ao número (não depende só de cor). */
export function Probability({ w, emphasis = false }: { w: WindowProbability | null; emphasis?: boolean }) {
  if (!w) {
    // Ressalva 4 do QA: janela malformada é sinalizada no lugar, sem descartar o item.
    return (
      <div className="min-w-[4.5rem]" role="group" aria-label="Janela com valor inválido na API">
        <span className={`font-semibold tracking-tight text-crit ${emphasis ? "text-lg" : "text-base"}`}>—</span>
        <div className="mt-1 h-1.5 w-full rounded-sm border border-dashed border-crit/40" aria-hidden="true" />
        <div className="mt-1 text-[11px] leading-4 text-crit">janela inválida</div>
      </div>
    );
  }
  const width = Math.round(w.probability * 100);
  // A API de produção ainda não calcula IC e manda os limites iguais à probabilidade.
  const hasCi = w.ci_low < w.ci_high;
  return (
    <div className="min-w-[4.5rem]">
      <div className="flex items-baseline gap-1">
        <span className={`tnum font-semibold tracking-tight ${emphasis ? "text-lg text-ink" : "text-base text-ink"}`}>
          {pct(w.probability)}
        </span>
      </div>
      <div
        className="mt-1 h-1.5 w-full overflow-hidden rounded-sm bg-primary-track"
        role="img"
        aria-label={hasCi ? `Intervalo de ${pct(w.ci_low)} a ${pct(w.ci_high)}` : "Intervalo de confiança indisponível"}
      >
        <div className="h-full rounded-sm bg-primary" style={{ width: `${width}%` }} />
      </div>
      <div className="tnum mt-1 text-[11px] leading-4 text-ink-3">{hasCi ? `${pct(w.ci_low)}–${pct(w.ci_high)}` : "IC indisponível"}</div>
    </div>
  );
}
