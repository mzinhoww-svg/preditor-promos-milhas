import { NextResponse } from "next/server";
import { getExplanation, type OfferType } from "@/lib/api";

export const dynamic = "force-dynamic";

const TYPES = new Set<OfferType>(["transfer_bonus", "purchase_discount", "boosted_accrual"]);
const NAME_RE = /^[\p{L}\p{N} .&'-]{1,64}$/u;

/**
 * Proxy server-side da explicação por item. A chave da API fica no servidor;
 * o cliente só vê esta rota. Parâmetros são validados antes de sair daqui.
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const origin = url.searchParams.get("origin") ?? "";
  const destination = url.searchParams.get("destination") ?? "";
  const type = url.searchParams.get("type") ?? "";
  if (!NAME_RE.test(origin) || !NAME_RE.test(destination) || !TYPES.has(type as OfferType)) {
    return NextResponse.json({ error: { code: "bad_request", message: "parâmetros inválidos" } }, { status: 400 });
  }
  const res = await getExplanation(origin, destination, type as OfferType);
  if (res.data) {
    return NextResponse.json({ data: res.data, origin: res.origin }, { headers: { "Cache-Control": "no-store" } });
  }
  const status = res.unavailable?.status === 404 ? 404 : 502;
  return NextResponse.json({ data: null, origin: res.origin, error: res.unavailable }, { status });
}
