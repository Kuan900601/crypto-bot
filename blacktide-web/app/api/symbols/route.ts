import { BYBIT_REST } from "@/lib/bybit";
export const dynamic = "force-dynamic";
let cache: { ts: number; body: unknown } | null = null;
const STOCKS: [string, string, string][] = [
  ["NVDA", "NVIDIA", "NASDAQ"], ["TSLA", "Tesla", "NASDAQ"], ["AAPL", "Apple", "NASDAQ"],
  ["MSFT", "Microsoft", "NASDAQ"], ["META", "Meta", "NASDAQ"], ["AMZN", "Amazon", "NASDAQ"],
  ["GOOGL", "Alphabet", "NASDAQ"], ["AMD", "AMD", "NASDAQ"], ["NFLX", "Netflix", "NASDAQ"],
  ["AVGO", "Broadcom", "NASDAQ"], ["INTC", "Intel", "NASDAQ"], ["PLTR", "Palantir", "NASDAQ"],
  ["COIN", "Coinbase", "NASDAQ"], ["MSTR", "MicroStrategy", "NASDAQ"], ["MU", "Micron", "NASDAQ"],
  ["QCOM", "Qualcomm", "NASDAQ"], ["ARM", "Arm", "NASDAQ"], ["SMCI", "Super Micro", "NASDAQ"],
  ["JPM", "JPMorgan", "NYSE"], ["V", "Visa", "NYSE"], ["MA", "Mastercard", "NYSE"],
  ["DIS", "Disney", "NYSE"], ["BA", "Boeing", "NYSE"], ["KO", "Coca-Cola", "NYSE"],
  ["WMT", "Walmart", "NYSE"], ["XOM", "Exxon", "NYSE"], ["BABA", "Alibaba", "NYSE"],
  ["NIO", "NIO", "NYSE"], ["UBER", "Uber", "NYSE"], ["SHOP", "Shopify", "NYSE"],
  ["SPY", "S&P 500 ETF", "AMEX"], ["QQQ", "Nasdaq 100 ETF", "NASDAQ"], ["IWM", "Russell 2000 ETF", "AMEX"],
  ["GLD", "Gold ETF", "AMEX"], ["TLT", "20Y Treasury ETF", "NASDAQ"], ["ARKK", "ARK Innovation", "AMEX"],
];
export async function GET() {
  if (cache && Date.now() - cache.ts < 3600000) return Response.json(cache.body);
  let crypto: { symbol: string; name: string; type: string; tvSymbol: string; bybit: string }[] = [];
  try {
    const r = await fetch(`${BYBIT_REST}/v5/market/instruments-info?category=linear&limit=1000`, { cache: "no-store" });
    const d = await r.json();
    const list = (d?.result?.list || []) as Record<string, string>[];
    crypto = list
      .filter((x) => x.quoteCoin === "USDT" && x.status === "Trading")
      .map((x) => ({ symbol: x.baseCoin, name: x.baseCoin, type: "crypto", tvSymbol: "BYBIT:" + x.symbol, bybit: x.symbol }));
  } catch {}
  const stocks = STOCKS.map(([s, n, ex]) => ({ symbol: s, name: n, type: "stock", tvSymbol: ex + ":" + s, bybit: null }));
  const body = { symbols: [...crypto, ...stocks], cryptoCount: crypto.length, source: crypto.length ? "bybit" : "stocks-only" };
  cache = { ts: Date.now(), body };
  return Response.json(body);
}
