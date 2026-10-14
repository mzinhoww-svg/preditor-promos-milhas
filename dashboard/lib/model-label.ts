import type { ComparisonDecision, Method, PredictionItem } from "./api/types";

export const METHOD_LABEL: Record<Method, string> = { b0: "B0 · taxa-base", b1: "B1 · hazard empírico" };

export interface ModelLabel {
  label: string;
  tone: "neutral" | "primary" | "warn";
  title: string;
}

/**
 * Selo do modelo em produção. Só B0 e B1 são mostrados como modelo; C1 (ou
 * qualquer outro nome) só aparece se a comparação campeão × desafiante o
 * promoveu. Fora disso o painel diz "não decidido" em vez de inventar.
 */
export function modelBadge(name: string, decision: ComparisonDecision | null): ModelLabel {
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

/**
 * Cabeçalho da lista (ressalva 2 do QA). O job nomeia a execução "B1" assim que
 * um par atinge 25 campanhas, mas os demais pares seguem em B0. Por isso:
 * - itens com método conhecido: um só método → esse método; mistura → "B0/B1 por par";
 * - método desconhecido nos itens: nome "B1" vira "B0/B1 por par", porque pode haver mistura;
 *   "B0" significa que nenhum par chegou ao B1; outro nome segue a regra do selo.
 */
export function headerModel(name: string, items: Pick<PredictionItem, "method">[], decision: ComparisonDecision | null): ModelLabel {
  const methods = new Set(items.map((i) => i.method).filter((m): m is Method => m === "b0" || m === "b1"));
  const known = items.length > 0 && items.every((i) => i.method === "b0" || i.method === "b1");
  const mixed: ModelLabel = {
    label: "B0/B1 por par",
    tone: "primary",
    title: "Pares com 25 ou mais campanhas usam B1 (hazard empírico); os demais, B0 (taxa-base). O método de cada item está em “Por que está na lista”.",
  };
  if (known) {
    if (methods.size > 1) return mixed;
    const only = [...methods][0];
    return modelBadge(only, decision);
  }
  if (methods.size > 1) return mixed;
  const n = name.trim().toLowerCase();
  if (n === "b1") return mixed;
  return modelBadge(name, decision);
}
