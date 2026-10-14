import { Badge } from "@/components/badge";
import { ageLabel, dateTime, isStale } from "@/lib/format";

/**
 * Idade do dado (ressalva 3 do QA): quando a API foi consultada e quando o
 * dado foi gerado. Dado gerado há mais de 36 h recebe o selo "dado velho".
 */
export function Freshness({
  origin,
  fetchedAt,
  generatedAt,
  now,
}: {
  origin: "mock" | "api";
  fetchedAt: string;
  generatedAt: string;
  now: Date;
}) {
  const stale = isStale(generatedAt, now);
  return (
    <p className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-3" aria-label="Idade dos dados">
      {origin === "api" ? (
        <>
          <span>
            API consultada <span className="text-ink-2">{ageLabel(fetchedAt, now)}</span>
          </span>
          <span aria-hidden="true">·</span>
        </>
      ) : null}
      <span>
        dados gerados <span className="text-ink-2">{ageLabel(generatedAt, now)}</span> ({dateTime(generatedAt)})
      </span>
      {stale ? (
        <Badge tone="warn" title="Gerado há mais de 36 h: o job diário pode não ter rodado">
          dado velho
        </Badge>
      ) : null}
    </p>
  );
}
