import { describe, expect, it } from "vitest";
import { comparisonLabel, headerModel, modelBadge, probabilityWord } from "../model-label";

describe("headerModel (ressalva 2: cabeçalho × item)", () => {
  it("mistura de métodos conhecidos vira 'B0/B1 por par (X em B1, Y em B0)'", () => {
    expect(headerModel("B1", [{ method: "b0" }, { method: "b1" }, { method: "b0" }], "keep_champion").label).toBe("B0/B1 por par (1 em B1, 2 em B0)");
    expect(headerModel("B1", [{ method: "b0" }, { method: "b1" }, { method: null }], null).label).toBe("B0/B1 por par (1 em B1, 1 em B0, 1 sem método)");
  });
  it("todos os itens no mesmo método mostram esse método", () => {
    expect(headerModel("B1", [{ method: "b0" }, { method: "b0" }], null).label).toBe("B0 · taxa-base");
    expect(headerModel("B0", [{ method: "b1" }], null).label).toBe("B1 · hazard empírico");
  });
  it("sem método nos itens, execução 'B1' pode misturar: 'B0/B1 por par'; 'B0' fica B0", () => {
    expect(headerModel("B1", [{ method: null }, { method: null }], null).label).toBe("B0/B1 por par");
    expect(headerModel("B0", [{ method: null }], null).label).toBe("B0 · taxa-base");
  });
  it("C1 segue a regra do selo: não decidido sem promoção, nome com promoção", () => {
    expect(headerModel("C1", [{ method: null }], "keep_champion").label).toBe("Modelo não decidido");
    expect(headerModel("C1", [{ method: null }], "promote_challenger").label).toBe("C1");
    expect(modelBadge("C1", null).tone).toBe("warn");
  });
});

describe("probabilityWord (1: só 'calibrada' com bins e is_calibrated)", () => {
  it("estimada sem métricas, sem bins ou sem flag; calibrada com os dois", () => {
    expect(probabilityWord(null)).toBe("estimada");
    expect(probabilityWord({ reliability: { horizon: 30, bins: [], is_calibrated: true } })).toBe("estimada");
    expect(probabilityWord({ reliability: { horizon: 30, bins: [{ p_mean: 0.1, observed: 0.1, n: 10 }], is_calibrated: false } })).toBe("estimada");
    expect(probabilityWord({ reliability: { horizon: 30, bins: [{ p_mean: 0.1, observed: 0.1, n: 10 }], is_calibrated: true } })).toBe("calibrada");
  });
});

describe("comparisonLabel (3: sem dados, sem Δ nem IC)", () => {
  it("sem dados com contagem conhecida", () => {
    const r = comparisonLabel({ has_data: false, decision: "keep_champion", note: "sem dados suficientes" }, { pair: "Livelo → Smiles", n_campaigns: 23, min: 25 });
    expect(r.value).toBe("Não decidido");
    expect(r.detail).toBe("dados insuficientes (Livelo → Smiles: 23 campanhas no treino, mínimo 25)");
    expect(comparisonLabel({ has_data: false, decision: "keep_champion", note: "x" }, { pair: null, n_campaigns: 23, min: 25 }).detail).toBe("dados insuficientes (23 campanhas no treino, mínimo 25)");
    expect(r.detail).not.toMatch(/Δ|IC/);
  });
  it("sem dados e sem contagem; com dados mostra a decisão", () => {
    expect(comparisonLabel({ has_data: false, decision: "keep_champion", note: "" }, { pair: null, n_campaigns: null, min: null }).detail).toBe("dados insuficientes (mínimo 25 campanhas por par)");
    expect(comparisonLabel({ has_data: true, decision: "keep_champion", note: "B1 segue" }, { pair: "A → B", n_campaigns: 40, min: 25 })).toEqual({ value: "Campeão mantido", detail: "B1 segue" });
  });
});
