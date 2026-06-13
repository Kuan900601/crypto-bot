import { NextRequest, NextResponse } from "next/server";
import { BYBIT_REST, coinBySymbol } from "@/lib/bybit";
import { Candle } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

// Bybit K 線代理（給 lightweight-charts 用）。symbol 用我們的代號（BTC…），interval 對 Bybit（15/60/240/D）。
const ALLOWED = new Set(["1", "5", "15", "60", "240", "D"]);

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const symbol = (sp.get("symbol") || "BTC").toUpperCase();
  const interval = sp.get("interval") || "60";
  const c = coinBySymbol(symbol);
  if (!c) return NextResponse.json({ candles: [], error: "unknown symbol" }, { status: 400 });
  if (!ALLOWED.has(interval)) return NextResponse.json({ candles: [], error: "bad interval" }, { status: 400 });

  try {
    const r = await fetch(
      `${BYBIT_REST}/v5/market/kline?category=linear&symbol=${c.bybit}&interval=${interval}&limit=200`,
      { cache: "no-store" }
    );
    if (!r.ok) return NextResponse.json({ candles: [], error: `HTTP ${r.status}` }, { status: 502 });
    const j = await r.json();
    const list: string[][] = j?.result?.list ?? [];
    // Bybit：[start, open, high, low, close, volume, turnover]，回傳新→舊；轉舊→新並除回原幣價
    const candles: Candle[] = list
      .map((k) => ({
        time: Math.floor(+k[0] / 1000),
        open: +k[1] / c.div, high: +k[2] / c.div, low: +k[3] / c.div, close: +k[4] / c.div,
      }))
      .reverse();
    return NextResponse.json({ candles, source: "bybit" });
  } catch (e) {
    return NextResponse.json({ candles: [], error: String(e) }, { status: 502 });
  }
}
