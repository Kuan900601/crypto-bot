import { BYBIT_REST } from "@/lib/bybit";
export const dynamic = "force-dynamic";
export async function GET(req: Request) {
  const symbol = new URL(req.url).searchParams.get("symbol") || "";
  if (!symbol) return Response.json({ ok: false });
  try {
    const r = await fetch(`${BYBIT_REST}/v5/market/tickers?category=linear&symbol=${symbol}`, { cache: "no-store" });
    const d = await r.json();
    const t = d?.result?.list?.[0];
    if (!t) return Response.json({ ok: false });
    return Response.json({
      ok: true,
      price: +t.lastPrice,
      changePct: +t.price24hPcnt * 100,
      high24h: +t.highPrice24h,
      low24h: +t.lowPrice24h,
      volume: +t.turnover24h,
      funding: t.fundingRate ? +t.fundingRate : null,
      oi: t.openInterestValue ? +t.openInterestValue : null,
    });
  } catch {
    return Response.json({ ok: false });
  }
}
