import type { ReactNode } from "react";

/** D1: contêiner rolável acessível por teclado (axe scrollable-region-focusable). */
export function ScrollRegion({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div
      tabIndex={0}
      role="region"
      aria-label={label}
      className={`overflow-x-auto rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 ${className ?? ""}`}
    >
      {children}
    </div>
  );
}
