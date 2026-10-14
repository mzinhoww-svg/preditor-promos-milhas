import { describe, expect, it } from "vitest";
import { ageLabel, isStale } from "../format";

const now = new Date("2026-10-14T12:00:00Z");

describe("idade do dado (ressalva 3)", () => {
  it("ageLabel em minutos, horas e dias", () => {
    expect(ageLabel("2026-10-14T11:59:50Z", now)).toBe("agora");
    expect(ageLabel("2026-10-14T11:55:00Z", now)).toBe("há 5 min");
    expect(ageLabel("2026-10-14T09:00:00Z", now)).toBe("há 3 h");
    expect(ageLabel("2026-10-12T12:00:00Z", now)).toBe("há 2 dias");
    expect(ageLabel(null, now)).toBe("—");
  });
  it("isStale marca dado gerado há mais de 36 h", () => {
    expect(isStale("2026-10-13T06:00:00Z", now)).toBe(false);
    expect(isStale("2026-10-12T20:00:00Z", now)).toBe(true);
    expect(isStale(null, now)).toBe(false);
  });
});
