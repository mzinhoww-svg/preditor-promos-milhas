import type { AlertKind, AlertSeverity, OfferType, SourceKind, SourceStatus } from "./api/types";

const ptBR = "pt-BR";

export function pct(value: number, digits = 0): string {
  // D6: valores minúsculos mas positivos não viram "0%".
  if (digits === 0 && value > 0 && value < 0.005) return "<1%";
  if (digits === 0 && value < 1 && value > 0.995) return ">99%";
  return new Intl.NumberFormat(ptBR, {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function num(value: number, digits = 3): string {
  return new Intl.NumberFormat(ptBR, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function int(value: number): string {
  return new Intl.NumberFormat(ptBR).format(value);
}

export function signed(value: number, digits = 3): string {
  const s = num(Math.abs(value), digits);
  if (value > 0) return `+${s}`;
  if (value < 0) return `−${s}`;
  return s;
}

export function dateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return new Intl.DateTimeFormat(ptBR, { day: "2-digit", month: "2-digit", timeZone: "UTC" }).format(d);
}

export function dateLong(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return new Intl.DateTimeFormat(ptBR, { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(d);
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(ptBR, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(new Date(iso)) + " UTC";
}

export function relativeFrom(iso: string | null | undefined, now: Date): string {
  if (!iso) return "—";
  const diffH = Math.round((now.getTime() - new Date(iso).getTime()) / 36e5);
  if (diffH < 1) return "há menos de 1 h";
  if (diffH < 48) return `há ${diffH} h`;
  return `há ${Math.round(diffH / 24)} dias`;
}

/** Idade curta de um instante: "agora", "há 5 min", "há 3 h", "há 2 dias". */
export function ageLabel(iso: string | null | undefined, now: Date): string {
  if (!iso) return "—";
  const ms = now.getTime() - new Date(iso).getTime();
  if (!Number.isFinite(ms)) return "—";
  const min = Math.round(ms / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `há ${h} h`;
  return `há ${Math.round(h / 24)} dias`;
}

/** Dado velho: gerado há mais de `maxHours` (o job é diário; 36 h cobre um atraso de meio dia). */
export function isStale(iso: string | null | undefined, now: Date, maxHours = 36): boolean {
  if (!iso) return false;
  const ms = now.getTime() - new Date(iso).getTime();
  return Number.isFinite(ms) && ms > maxHours * 36e5;
}

export const OFFER_TYPE_LABEL: Record<OfferType, string> = {
  transfer_bonus: "Bônus de transferência",
  purchase_discount: "Compra com desconto",
  boosted_accrual: "Acúmulo turbinado",
};

export const OFFER_TYPE_SHORT: Record<OfferType, string> = {
  transfer_bonus: "Transferência",
  purchase_discount: "Compra",
  boosted_accrual: "Acúmulo",
};

export const SOURCE_STATUS_LABEL: Record<SourceStatus, string> = {
  ok: "Operando",
  degraded: "Degradada",
  stale: "Parada",
  blocked: "Bloqueada",
  error: "Com erro",
};

export const SOURCE_KIND_LABEL: Record<SourceKind, string> = {
  rss: "RSS",
  html: "HTML",
  wayback: "Wayback",
  official: "Oficial",
};

export const SEVERITY_LABEL: Record<AlertSeverity, string> = {
  critical: "Crítico",
  warning: "Atenção",
  info: "Informativo",
};

export const ALERT_KIND_LABEL: Record<AlertKind, string> = {
  drift: "Drift do modelo",
  source: "Fonte",
  budget: "Orçamento",
  pipeline: "Pipeline",
  model: "Modelo",
};
