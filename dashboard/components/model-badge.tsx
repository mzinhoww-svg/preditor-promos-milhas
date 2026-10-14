import { Badge } from "@/components/badge";
import type { ComparisonDecision, Method, PredictionItem } from "@/lib/api";
import { METHOD_LABEL, headerModel, modelBadge } from "@/lib/model-label";

export { METHOD_LABEL, headerModel, modelBadge };

export function ModelBadge({ name, decision }: { name: string; decision: ComparisonDecision | null }) {
  const b = modelBadge(name, decision);
  return (
    <Badge tone={b.tone} title={b.title}>
      {b.label}
    </Badge>
  );
}

/** Selo do cabeçalho da lista: "B0/B1 por par" quando a execução mistura métodos. */
export function HeaderModelBadge({ name, items, decision }: { name: string; items: Pick<PredictionItem, "method">[]; decision: ComparisonDecision | null }) {
  const b = headerModel(name, items, decision);
  return (
    <Badge tone={b.tone} title={b.title}>
      {b.label}
    </Badge>
  );
}

export function MethodBadge({ method }: { method: Method }) {
  return (
    <Badge tone={method === "b1" ? "primary" : "neutral"} title={method === "b1" ? "Hazard empírico (25 ou mais campanhas)" : "Taxa-base (menos de 25 campanhas)"}>
      {METHOD_LABEL[method]}
    </Badge>
  );
}
