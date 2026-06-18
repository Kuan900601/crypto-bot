export const dynamic = "force-dynamic";

const STOCKS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "AMD"];
const cache = new Map<string, { ts: number; data: unknown }>();
const CACHE_TTL = 60000;

function calcRSI(closes: number[], period = 14): number {
  if (closes.length < period + 1) return 50;
  let gains = 0, losses = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    if (d > 0) gains += d; else losses -= d;
  }
  const avgG = gains / period, avgL = losses / period;
  if (avgL === 0) return 100;
  const rs = avgG / avgL;
  return Math.round(100 - 100 / (1 + rs));
}

function calcMA(closes: number[], period: number): number {
  if (closes.length < period) return closes[closes.length - 1] ?? 0;
  const sl = closes.slice(-period);
  return sl.reduce((a, b) => a + b, 0) / period;
}

function calcATR(highs: number[], lows: number[], closes: number[], period = 14): number {
  if (highs.length < 2) return 0;
  let sum = 0; const n = Math.min(period, highs.length - 1);
  for (let i = highs.length - n; i < highs.length; i++) {
    const tr = Math.max(highs[i] - lows[i], Math.abs(highs[i] - closes[i - 1]), Math.abs(lows[i] - closes[i - 1]));
    sum += tr;
  }
  return sum / n;
}

async function fetchYahoo(symbol: string) {
  const c = cache.get(symbol);
  if (c && Date.now() - c.ts < CACHE_TTL) return c.data;
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=60d`;
  const r = await fetch(url, { cache: "no-store", headers: { "User-Agent": "Mozilla/5.0" } });
  if (!r.ok) throw new Error("yahoo " + r.status);
  const json = await r.json();
  const result = json?.chart?.result?.[0];
  if (!result) throw new Error("no result");
  const meta = result.meta;
  const ts: number[] = result.timestamp ?? [];
  const q = result.indicators?.quote?.[0] ?? {};
  const closes: number[] = (q.close ?? []).map(Number);
  const highs: number[] = (q.high ?? []).map(Number);
  const lows: number[] = (q.low ?? []).map(Number);
  const volumes: number[] = (q.volume ?? []).map(Number);
  const price = meta.regularMarketPrice ?? closes[closes.length - 1] ?? 0;
  const prevClose = meta.chartPreviousClose ?? closes[closes.length - 2] ?? price;
  const change24h = prevClose ? ((price - prevClose) / prevClose) * 100 : 0;
  const rsi = calcRSI(closes);
  const ma20 = calcMA(closes, 20);
  const ma50 = calcMA(closes, 50);
  const atr = calcATR(highs, lows, closes);
  const atrPct = price ? (atr / price) * 100 : 0;
  const momentum = closes.length >= 5 ? ((closes[closes.length - 1] - closes[closes.length - 5]) / closes[closes.length - 5]) * 100 : 0;
  const trend = ma20 > ma50 ? "up" : ma20 < ma50 ? "down" : "flat";
  const bias = rsi >= 60 && trend === "up" ? "long" : rsi <= 40 && trend === "down" ? "short" : "neutral";
  const confidence = Math.min(90, Math.abs(rsi - 50) + 50);
  const risk = atrPct > 2.5 ? 70 : atrPct > 1.5 ? 50 : 30;
  const high52 = meta.fiftyTwoWeekHigh ?? Math.max(...highs);
  const low52 = meta.fiftyTwoWeekLow ?? Math.min(...lows);
  const vol = volumes[volumes.length - 1] ?? 0;
  const avgVol = volumes.length ? volumes.slice(-20).reduce((a, b) => a + b, 0) / Math.min(20, volumes.length) : 0;
  const volRatio = avgVol ? vol / avgVol : 1;

  let action = "";
  if (bias === "long") action = `RSI ${rsi} 偏強，均線多頭排列（MA20 $${ma20.toFixed(2)} > MA50 $${ma50.toFixed(2)}），動能正向 ${momentum >= 0 ? "+" : ""}${momentum.toFixed(1)}%。建議觀察量能配合，可考慮逢低布局，止損參考近期低點。`;
  else if (bias === "short") action = `RSI ${rsi} 偏弱，均線空頭排列（MA20 $${ma20.toFixed(2)} < MA50 $${ma50.toFixed(2)}），動能疲軟 ${momentum.toFixed(1)}%。謹慎操作，等待反彈確認或跌破支撐後再做空。`;
  else action = `RSI ${rsi} 中性區間，MA20 $${ma20.toFixed(2)} 與 MA50 $${ma50.toFixed(2)} 纏繞，方向待確認。建議持倉觀望或設定突破條件再進場。`;

  const support = [+(price * 0.97).toFixed(2), +(price * 0.94).toFixed(2)];
  const resistance = [+(price * 1.03).toFixed(2), +(price * 1.06).toFixed(2)];

  const data = {
    ok: true,
    symbol,
    name: meta.longName ?? meta.shortName ?? symbol,
    price: +price.toFixed(2),
    change24h: +change24h.toFixed(2),
    rsi,
    ma20: +ma20.toFixed(2),
    ma50: +ma50.toFixed(2),
    atrPct: +atrPct.toFixed(2),
    momentum: +momentum.toFixed(2),
    trend,
    bias,
    confidence: Math.round(confidence),
    risk,
    high52: +high52.toFixed(2),
    low52: +low52.toFixed(2),
    vol,
    volRatio: +volRatio.toFixed(2),
    support,
    resistance,
    action,
  };
  cache.set(symbol, { ts: Date.now(), data });
  return data;
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const symbol = (searchParams.get("symbol") ?? "AAPL").toUpperCase();
  if (!STOCKS.includes(symbol)) return Response.json({ ok: false, error: "unsupported" }, { status: 400 });
  try {
    const data = await fetchYahoo(symbol);
    return Response.json(data);
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
