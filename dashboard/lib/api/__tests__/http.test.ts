import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, FETCH_INIT, getJson } from "../http";

describe("getJson (ressalva 3: sem cache de dados)", () => {
  beforeEach(() => {
    process.env.PREDITOR_API_BASE_URL = "http://api.test/v1";
    process.env.PREDITOR_API_KEY = "k";
  });
  afterEach(() => vi.unstubAllGlobals());

  it("chama a API sem cache e sem revalidate, com a chave no header", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: 1 }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await getJson("/predictions", { type: "transfer_bonus" });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit & { next?: unknown }];
    expect(String(url)).toBe("http://api.test/v1/predictions?type=transfer_bonus");
    expect(init.cache).toBe("no-store");
    expect(init.next).toBeUndefined();
    expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("k");
    expect(FETCH_INIT.cache).toBe("no-store");
  });

  it("erro HTTP vira ApiError com código do corpo", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { code: "RATE_LIMITED", message: "x" } }), { status: 429 })));
    await expect(getJson("/predictions")).rejects.toMatchObject({ status: 429, code: "RATE_LIMITED" } satisfies Partial<ApiError>);
  });
});
