import { pct } from "@/lib/format";
import type { WindowProbability } from "@/lib/api/types";

/** Probabilidade com barra e intervalo. A barra é redundante ao número (não depende só de cor). */
export function Probability({ w, emphasis = false }: { w: WindowProbability; emphasis?: boolean }) {
  const width = Math.round(w.probability * 100);
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
        aria-label={`Intervalo de ${pct(w.ci_low)} a ${pct(w.ci_high)}`}
      >
        <div className="h-full rounded-sm bg-primary" style={{ width: `${width}%` }} />
      </div>
      <div className="tnum mt-1 text-[11px] leading-4 text-ink-3">
        {pct(w.ci_low)}–{pct(w.ci_high)}
      </div>
    </div>
  );
}
