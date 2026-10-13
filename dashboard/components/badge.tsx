import type { AlertSeverity, SourceStatus } from "@/lib/api/types";

type Tone = "neutral" | "ok" | "warn" | "crit" | "info" | "primary";

const TONE: Record<Tone, string> = {
  neutral: "border-line bg-surface-2 text-ink-2",
  ok: "border-ok/30 bg-ok-soft text-ok",
  warn: "border-warn/30 bg-warn-soft text-warn",
  crit: "border-crit/30 bg-crit-soft text-crit",
  info: "border-info/30 bg-info-soft text-info",
  primary: "border-primary/30 bg-primary-soft text-primary",
};

export function Badge({
  tone = "neutral",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      title={title ?? (typeof children === "string" ? children : undefined)}
      className={`inline-flex max-w-full items-center truncate whitespace-nowrap rounded border px-1.5 py-0.5 text-xs font-medium leading-4 ${TONE[tone]}`}
    >
      {children}
    </span>
  );
}

export const STATUS_TONE: Record<SourceStatus, Tone> = {
  ok: "ok",
  degraded: "warn",
  stale: "neutral",
  blocked: "crit",
  error: "crit",
};

export const SEVERITY_TONE: Record<AlertSeverity, Tone> = {
  critical: "crit",
  warning: "warn",
  info: "info",
};
