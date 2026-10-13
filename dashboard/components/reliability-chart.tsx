import { pct } from "@/lib/format";

/**
 * Curva de confiabilidade: previsto (x) × observado (y). Diagonal = calibração perfeita.
 * SVG puro, com tabela de dados escondida para leitores de tela.
 */
export function ReliabilityChart({
  bins,
  horizon,
}: {
  bins: { p_mean: number; observed: number; n: number }[];
  horizon: number;
}) {
  const W = 420;
  const H = 320;
  const m = { top: 16, right: 16, bottom: 40, left: 44 };
  const iw = W - m.left - m.right;
  const ih = H - m.top - m.bottom;
  const x = (v: number) => m.left + v * iw;
  const y = (v: number) => m.top + (1 - v) * ih;
  const maxN = Math.max(...bins.map((b) => b.n), 1);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const path = bins.map((b, i) => `${i === 0 ? "M" : "L"}${x(b.p_mean).toFixed(1)},${y(b.observed).toFixed(1)}`).join(" ");

  return (
    <figure className="min-w-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full max-w-[520px]"
        role="img"
        aria-labelledby="rel-title rel-desc"
      >
        <title id="rel-title">{`Curva de confiabilidade, horizonte de ${horizon} dias`}</title>
        <desc id="rel-desc">
          {"Probabilidade prevista no eixo horizontal e frequência observada no eixo vertical. Pontos próximos da diagonal indicam boa calibração."}
        </desc>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.left} x2={W - m.right} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
            <text x={m.left - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--ink-3)">
              {Math.round(t * 100)}%
            </text>
            <text x={x(t)} y={H - m.bottom + 18} textAnchor="middle" fontSize={11} fill="var(--ink-3)">
              {Math.round(t * 100)}%
            </text>
          </g>
        ))}
        <line
          x1={x(0)}
          y1={y(0)}
          x2={x(1)}
          y2={y(1)}
          stroke="var(--line-strong)"
          strokeWidth={1}
          strokeDasharray="4 4"
        />
        <path d={path} fill="none" stroke="var(--primary)" strokeWidth={2} strokeLinejoin="round" />
        {bins.map((b) => (
          <circle
            key={b.p_mean}
            cx={x(b.p_mean)}
            cy={y(b.observed)}
            r={3 + (b.n / maxN) * 5}
            fill="var(--bg)"
            stroke="var(--primary)"
            strokeWidth={2}
          />
        ))}
        <text x={m.left + iw / 2} y={H - 4} textAnchor="middle" fontSize={11} fill="var(--ink-2)">
          Probabilidade prevista
        </text>
        <text
          transform={`translate(12 ${m.top + ih / 2}) rotate(-90)`}
          textAnchor="middle"
          fontSize={11}
          fill="var(--ink-2)"
        >
          Frequência observada
        </text>
      </svg>
      <figcaption className="mt-2 text-xs text-ink-3">
        Tamanho do ponto proporcional ao número de predições no bin. Linha tracejada: calibração perfeita.
      </figcaption>
      <ul className="sr-only" aria-label="Dados da curva de confiabilidade">
        {bins.map((b, i) => (
          <li key={`${i}-${b.p_mean}`}>
            {`previsto ${pct(b.p_mean)}, observado ${pct(b.observed)}, ${b.n} predições`}
          </li>
        ))}
      </ul>
    </figure>
  );
}
