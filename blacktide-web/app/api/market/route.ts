import { COINS, BYBIT_REST } from "@/lib/bybit";
import { TICKERS as MOCK } from "@/lib/mock";
import { Ticker, MarketStats } from "@/lib/types";
export const dynamic = "force-dynamic";
let cache: { ts: number; body: unknown } | null = null;
async function j(url: string) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}
async function cryptoTickers(): Promise<{ list: Ticker[]; src: string }> {
  try {
    const d = await j(`${BYBIT_REST}/v5/market/tickers?category=linear`);
    const map = new Map<string, Record<string, string>>(
      (d.result.list as Record<string, string>[]).map((x) => [x.symbol, x])
    );
    const sparks = await Promise.all(COINS.map(async (c) => {
      try {
        const k = await j(`${BYBIT_REST}/v5/market/kline?category=linear&symbol=${c.bybit}&interval=15&limit=36`);
        return (k.result.list as string[][]).map((b) => +b[4] / c.div).reverse();
      } catch { return [] as number[]; }
    }));
    const list: Ticker[] = [];
    COINS.forEach((c, i) => {
      const t = map.get(c.bybit);
      if (!t) return;
      const price = +t.lastPrice / c.div;
      list.push({
        symbol: c.symbol, name: c.name, class: "crypto",
        price, changePct: +t.price24hPcnt * 100, volume: +t.turnover24h,
        openInterest: t.openInterestValue ? +t.openInterestValue : undefined,
        fundingRate: t.fundingRate ? +t.fundingRate : undefined,
        spark: sparks[i].length ? sparks[i] : Array(36).fill(price),
        tvSymbol: "BYBIT:" + c.bybit,
      });
    });
    if (!list.length) throw new Error("empty");
    return { list, src: "bybit" };
  } catch {
    return { list: MOCK.filter((t) => t.class === "crypto"), src: "mock" };
  }
}
async function stockTickers(): Promise<{ list: Ticker[]; src: string }> {
  const base = MOCK.filter((t) => t.class === "stock");
  const key = process.env.FINNHUB_API_KEY;
  if (!key) return { list: base, src: "demo" };
  try {
    const list = await Promise.all(base.map(async (s) => {
      const q = await j(`https://finnhub.io/api/v1/quote?symbol=${s.symbol}&token=${key}`);
      return { ...s, price: q.c || s.price, changePct: typeof q.dp === "number" ? q.dp : s.changePct };
    }));
    return { list, src: "finnhub" };
  } catch { return { list: base, src: "demo" }; }
}
async function buildStats(btc?: Ticker): Promise<MarketStats> {
  let fearGreed = 50, btcDominance = 0;
  try { const f = await j("https://api.alternative.me/fng/?limit=1"); fearGreed = +f.data[0].value; } catch {}
  try { const g = await j("https://api.coingecko.com/api/v3/global"); btcDominance = +(+g.data.market_cap_percentage.btc).toFixed(1); } catch {}
  return { fearGreed, btcDominance, btcTurnover: btc?.volume ?? 0, btcFunding: btc?.fundingRate };
}
export async function GET() {
  if (cache && Date.now() - cache.ts < 10000) return Response.json(cache.body);
  const [c, s] = await Promise.all([cryptoTickers(), stockTickers()]);
  const body = {
    tickers: [...c.list, ...s.list],
    stats: await buildStats(c.list.find((t) => t.symbol === "BTC")),
    source: { crypto: c.src, stocks: s.src },
  };
  cache = { ts: Date.now(), body };
  return Response.json(body);
}
