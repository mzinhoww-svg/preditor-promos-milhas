import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

/**
 * Guardas de texto (revisão do Planejador no PR #56): falham se uma frase que
 * promete mais do que o modelo sabe voltar ao código.
 */
const read = (p: string) => readFileSync(new URL(`../../${p}`, import.meta.url), "utf8");
const layout = read("app/layout.tsx");
const page = read("app/page.tsx");
const list = read("components/prediction-list.tsx");
const modelo = read("app/modelo/page.tsx");
const strip = read("components/status-strip.tsx");

describe("textos honestos", () => {
  it("(1) 'probabilidade calibrada' não é afirmada; 'estimada' é o padrão", () => {
    for (const src of [layout, page]) expect(src).not.toMatch(/probabilidade(s)? calibrada|chance calibrada/i);
    expect(layout).toContain("probabilidade estimada");
    expect(layout).toContain("Probabilidades estimadas");
    expect(page).toContain("probabilityWord(");
  });
  it("(2) bônus é histórico, não previsto", () => {
    for (const src of [page, list]) expect(src).not.toMatch(/b[ôo]nus previsto|quartis do b[ôo]nus previsto|faixa prevista/i);
    expect(list.split("Bônus nas campanhas anteriores (P25 · P50 · P75)").length - 1).toBe(2);
    expect(list).toContain("mediana e quartis dos bônus anteriores");
    expect(page).toContain("mediana histórica ");
    expect(page).toContain("quartis dos bônus nas campanhas anteriores");
  });
  it("(3) comparação sem dados nunca mostra Δ nem IC fora de cmp.has_data", () => {
    expect(modelo).toContain("comparisonLabel(");
    expect(modelo).toContain("{cmp.has_data ? (");
    expect(modelo).not.toMatch(/"Sem dados"/);
  });
  it("(4) cabeçalho por par e campeão nulo tolerado no /modelo", () => {
    expect(page).toContain("HeaderModelBadge");
    expect(modelo).toContain("Modelo não decidido");
    expect(modelo).toContain("servindo ${serving.label}");
    expect(modelo).toContain("m.champion ??");
  });
  it("não bloqueantes: contexto histórico, amostra pequena e 'dados de HH:MM'", () => {
    expect(page).toContain("contexto histórico do par");
    expect(page).not.toContain("fatores que o colocaram ali");
    expect(modelo).toContain("amostra pequena (n < 30)");
    expect(strip).toContain("dados de {timeUTC(runAt)}");
  });
});
