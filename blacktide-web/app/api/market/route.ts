import { NextResponse } from "next/server";
import { TICKERS, MARKET_STATS } from "@/lib/mock";

export const dynamic = "force-dynamic";

// Mock 行情。真實行情可在此接 Binance/交易所公開 API；此處不影響策略，純展示層。
export async function GET() {
  return NextResponse.json({ tickers: TICKERS, stats: MARKET_STATS });
}
