import { describe, expect, it } from "vitest";
import { headerModel, modelBadge } from "../model-label";

describe("headerModel (ressalva 2: cabeçalho × item)", () => {
  it("mistura de métodos conhecidos vira 'B0/B1 por par'", () => {
    expect(headerModel("B1", [{ method: "b0" }, { method: "b1" }], "keep_champion").label).toBe("B0/B1 por par");
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
