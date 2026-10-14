import { Badge } from "@/components/badge";
import type { ComparisonDecision, Method } from "@/lib/api";

export const METHOD_LABEL: Record<Method, string> = { b0: "B0 · taxa-base", b1: "B1 · hazard empírico" };

/**
 * Selo do modelo em produção. Só B0 e B1 são mostrados como modelo; C1 (ou
 * qualquer outro nome) só aparece se a comparação campeão × desafiante o
 * promoveu. Fora disso o painel diz "não decidido" em vez de inventar.
 */
export function modelBadge(name: string, decision: ComparisonDecision | null): { label: string; tone: "neutral" | "primary" | "warn"; title: string } {
  const n = name.trim().toLowerCase();
  if (n === "b0") return { label: METHOD_LABEL.b0, tone: "neutral", title: "Taxa-base histórica do par; usado quando há menos de 25 campanhas." };
  if (n === "b1") return { label: METHOD_LABEL.b1, tone: "primary", title: "Hazard empírico por intervalo e sazonalidade; exige 25 ou mais campanhas." };
  if (decision === "promote_challenger") return { label: name, tone: "primary", title: "Desafiante promovido na comparação campeão × desafiante." };
  return {
    label: "Modelo não decidido",
    tone: "warn",
    title: `A API informa "${name}", mas só B0 e B1 estão decididos para produção. C1 entra depois de vencer B1 em Brier e log-loss com intervalo de confiança.`,
  };
}

export function ModelBadge({ name, decision }: { name: string; decision: ComparisonDecision | null }) {
  const b = modelBadge(name, decision);
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
