import { NextResponse } from "next/server";
import { TICKERS, MARKET_STATS } from "@/lib/mock";
import { COINS, BYBIT_REST } from "@/lib/bybit";
import { Ticker, MarketStats, MarketResponse } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

// 真實行情：Bybit 公開 REST（永續），抓不到自動退回 mock。純展示層，不影響策略。
// macro（恐懼貪婪、BTC 佔比）走免金鑰公開 API；失敗沿用 mock 值。

interface BybitTickerRow {
  symbol: string; lastPrice: string; price24hPcnt: string;
  turnover24h: string; openInterest: string; openInterestValue?: string; fundingRate: string;
}

async function fetchBybitTickers(): Promise<Ticker[] | null> {
  try {
    const r = await fetch(`${BYBIT_REST}/v5/market/tickers?category=linear`, { cache: "no-store" });
    if (!r.ok) return null;
    const j = await r.json();
    const rows: BybitTickerRow[] = j?.result?.list ?? [];
    const byBybit = new Map(rows.map((x) => [x.symbol, x]));

    // 每個幣抓一小段 K 線當 spark（並行）；個別失敗就退空陣列由前端容錯
    const tickers = await Promise.all(
      COINS.map(async (c) => {
        const row = byBybit.get(c.bybit);
        if (!row) return null;
        const price = +row.lastPrice / c.div;
        const oiBase = +(row.openInterestValue ?? "0") || +row.openInterest * +row.lastPrice;
        let spark: number[] = [];
        try {
          const kr = await fetch(
            `${BYBIT_REST}/v5/market/kline?category=linear&symbol=${c.bybit}&interval=15&limit=36`,
            { cache: "no-store" }
          );
          if (kr.ok) {
            const kj = await kr.json();
            const list: string[][] = kj?.result?.list ?? [];
            // Bybit 回傳新→舊，反轉成舊→新；close 在索引 4
            spark = list.map((row2) => +row2[4] / c.div).reverse();
          }
        } catch { /* spark 失敗不影響其他欄位 */ }
        const t: Ticker = {
          symbol: c.symbol, name: c.name, class: "crypto",
          price, changePct: +row.price24hPcnt * 100,
          volume: +row.turnover24h, openInterest: oiBase,
          fundingRate: +row.fundingRate,
          spark, tvSymbol: `BYBIT:${c.bybit}.P`,
        };
        return t;
      })
    );
    const out = tickers.filter((t): t is Ticker => t !== null);
    return out.length ? out : null;
  } catch {
    return null;
  }
}

async function fetchMacro(): Promise<{ fearGreed?: number; btcDominance?: number; live: boolean }> {
  let fearGreed: number | undefined;
  let btcDominance: number | undefined;
  try {
    const r = await fetch("https://api.alternative.me/fng/?limit=1", { cache: "no-store" });
    if (r.ok) { const j = await r.json(); fearGreed = +j?.data?.[0]?.value || undefined; }
  } catch { /* 沿用 mock */ }
  try {
    const r = await fetch("https://api.coingecko.com/api/v3/global", { cache: "no-store" });
    if (r.ok) { const j = await r.json(); btcDominance = j?.data?.market_cap_percentage?.btc; }
  } catch { /* 沿用 mock */ }
  return { fearGreed, btcDominance, live: fearGreed !== undefined || btcDominance !== undefined };
}

export async function GET() {
  const [bybit, macro] = await Promise.all([fetchBybitTickers(), fetchMacro()]);

  const tickers = bybit ?? TICKERS;
  const btc = tickers.find((t) => t.symbol === "BTC");
  const stats: MarketStats = {
    ...MARKET_STATS,
    fearGreed: macro.fearGreed ?? MARKET_STATS.fearGreed,
    btcDominance: macro.btcDominance != null ? +macro.btcDominance.toFixed(1) : MARKET_STATS.btcDominance,
    btcTurnover: btc?.volume,
    btcFunding: btc?.fundingRate,
  };

  const body: MarketResponse = {
    tickers,
    stats,
    source: { crypto: bybit ? "bybit" : "mock", macro: macro.live ? "live" : "mock" },
  };
  return NextResponse.json(body);
}
