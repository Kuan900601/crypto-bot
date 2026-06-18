export const dynamic = "force-dynamic";

const STOCKS_META: Record<string, { name: string; sector: string; peers: string[] }> = {
  AAPL: { name: "Apple Inc.", sector: "科技 · 消費電子", peers: ["MSFT", "GOOGL"] },
  MSFT: { name: "Microsoft Corp.", sector: "科技 · 雲端/AI", peers: ["AAPL", "GOOGL"] },
  NVDA: { name: "NVIDIA Corp.", sector: "科技 · AI 晶片", peers: ["AMD", "MSFT"] },
  TSLA: { name: "Tesla Inc.", sector: "電動車 · 能源", peers: ["AAPL", "AMZN"] },
  AMZN: { name: "Amazon.com Inc.", sector: "電商 · 雲端", peers: ["MSFT", "GOOGL"] },
  META: { name: "Meta Platforms", sector: "社交媒體 · AI", peers: ["GOOGL", "MSFT"] },
  GOOGL: { name: "Alphabet Inc.", sector: "搜尋 · 雲端 · AI", peers: ["MSFT", "META"] },
  AMD: { name: "Advanced Micro Devices", sector: "半導體 · AI 晶片", peers: ["NVDA", "MSFT"] },
};

const STOCKS = Object.keys(STOCKS_META);
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
  return Math.round(100 - 100 / (1 + avgG / avgL));
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
function calcBollinger(closes: number[], period = 20): { upper: number; mid: number; lower: number } {
  const sl = closes.slice(-period);
  const mid = sl.reduce((a, b) => a + b, 0) / sl.length;
  const variance = sl.reduce((a, b) => a + (b - mid) ** 2, 0) / sl.length;
  const std = Math.sqrt(variance) * 2;
  return { upper: mid + std, mid, lower: mid - std };
}
function calcMacd(closes: number[]): { macd: number; signal: number; hist: number } {
  const ema = (arr: number[], p: number) => {
    const k = 2 / (p + 1);
    let e = arr[0];
    for (let i = 1; i < arr.length; i++) e = arr[i] * k + e * (1 - k);
    return e;
  };
  if (closes.length < 26) return { macd: 0, signal: 0, hist: 0 };
  const e12 = ema(closes, 12), e26 = ema(closes, 26);
  const macd = e12 - e26;
  const signal = macd * (2 / 10); // simplified
  return { macd: +macd.toFixed(3), signal: +signal.toFixed(3), hist: +(macd - signal).toFixed(3) };
}

async function fetchYahoo(symbol: string) {
  const c = cache.get(symbol);
  if (c && Date.now() - c.ts < CACHE_TTL) return c.data;
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=90d`;
  const r = await fetch(url, { cache: "no-store", headers: { "User-Agent": "Mozilla/5.0" } });
  if (!r.ok) throw new Error("yahoo " + r.status);
  const json = await r.json();
  const result = json?.chart?.result?.[0];
  if (!result) throw new Error("no result");
  const meta = result.meta;
  const q = result.indicators?.quote?.[0] ?? {};
  const closes: number[] = (q.close ?? []).map(Number).filter(Boolean);
  const highs: number[] = (q.high ?? []).map(Number).filter(Boolean);
  const lows: number[] = (q.low ?? []).map(Number).filter(Boolean);
  const volumes: number[] = (q.volume ?? []).map(Number).filter(Boolean);
  const price = meta.regularMarketPrice ?? closes[closes.length - 1] ?? 0;
  const prevClose = meta.chartPreviousClose ?? closes[closes.length - 2] ?? price;
  const change24h = prevClose ? ((price - prevClose) / prevClose) * 100 : 0;
  const rsi = calcRSI(closes);
  const ma20 = calcMA(closes, 20);
  const ma50 = calcMA(closes, 50);
  const ma200 = calcMA(closes, Math.min(200, closes.length));
  const atr = calcATR(highs, lows, closes);
  const atrPct = price ? (atr / price) * 100 : 0;
  const momentum5 = closes.length >= 5 ? ((closes[closes.length - 1] - closes[closes.length - 5]) / closes[closes.length - 5]) * 100 : 0;
  const momentum20 = closes.length >= 20 ? ((closes[closes.length - 1] - closes[closes.length - 20]) / closes[closes.length - 20]) * 100 : 0;
  const boll = calcBollinger(closes);
  const macd = calcMacd(closes);
  const trend = ma20 > ma50 ? (ma50 > ma200 ? "up" : "up_weak") : ma20 < ma50 ? (ma50 < ma200 ? "down" : "down_weak") : "flat";
  const trendSimple = trend.startsWith("up") ? "up" : trend.startsWith("down") ? "down" : "flat";
  const bias = rsi >= 60 && trendSimple === "up" ? "long" : rsi <= 40 && trendSimple === "down" ? "short" : "neutral";
  const confidence = Math.min(90, Math.abs(rsi - 50) + 50);
  const risk = atrPct > 2.5 ? 70 : atrPct > 1.5 ? 50 : 30;
  const high52 = meta.fiftyTwoWeekHigh ?? Math.max(...highs);
  const low52 = meta.fiftyTwoWeekLow ?? Math.min(...lows);
  const range52Pct = high52 > low52 ? ((price - low52) / (high52 - low52)) * 100 : 50;
  const vol = volumes[volumes.length - 1] ?? 0;
  const avgVol = volumes.length ? volumes.slice(-20).reduce((a, b) => a + b, 0) / Math.min(20, volumes.length) : 0;
  const volRatio = avgVol ? vol / avgVol : 1;
  const bollPct = boll.upper > boll.lower ? ((price - boll.lower) / (boll.upper - boll.lower)) * 100 : 50;

  const meta2 = STOCKS_META[symbol] ?? { name: symbol, sector: "科技", peers: [] };

  // Generate detailed action text
  let action = "";
  const trendText = trend === "up" ? "均線呈多頭排列（MA20 > MA50 > MA200），強勢格局" :
                    trend === "up_weak" ? "MA20 站上 MA50，但 MA200 尚未突破，趨勢轉多初期" :
                    trend === "down" ? "均線呈空頭排列（MA20 < MA50 < MA200），弱勢格局" :
                    trend === "down_weak" ? "MA20 跌破 MA50，趨勢轉弱，小心進一步下跌" :
                    "均線纏繞糾結，趨勢方向不明，等待突破";
  const rsiText = rsi >= 70 ? `RSI ${rsi} 超買區間，需警惕短線回調壓力` :
                  rsi <= 30 ? `RSI ${rsi} 超賣區間，可能出現技術性反彈` :
                  rsi >= 60 ? `RSI ${rsi} 偏強，仍在上升動能區間` :
                  rsi <= 40 ? `RSI ${rsi} 偏弱，賣方力道較強` :
                  `RSI ${rsi} 中性，多空力量相對平衡`;
  const volText = volRatio > 1.5 ? `近期成交量是均量 ${volRatio.toFixed(1)} 倍，市場關注度明顯放大` :
                  volRatio < 0.7 ? "成交量萎縮，市場觀望情緒濃厚" : "成交量接近均值，正常波動";
  const bollText = bollPct > 80 ? "股價接近布林通道上軌，短線有壓" :
                   bollPct < 20 ? "股價接近布林通道下軌，有技術支撐" :
                   "股價位於布林通道中段，觀察方向選擇";
  const macdText = macd.hist > 0 ? `MACD 柱狀圖翻正（${macd.hist > 0 ? "+" : ""}${macd.hist}），短線動能向上` :
                   `MACD 柱狀圖為負（${macd.hist}），短線動能偏弱`;

  if (bias === "long") {
    action = `${trendText}。${rsiText}。${volText}。${bollText}。${macdText}。綜合來看，${symbol} 目前技術面偏多，可考慮在回測支撐時逢低布局，設止損於近期低點。`;
  } else if (bias === "short") {
    action = `${trendText}。${rsiText}。${volText}。${bollText}。${macdText}。技術面偏空，短線不宜追多，等待反彈確認壓力後再考慮做空，或觀望至趨勢明朗。`;
  } else {
    action = `${trendText}。${rsiText}。${volText}。${bollText}。${macdText}。目前技術面中性，建議觀望等待方向確認，突破前高或跌破支撐後再行動。`;
  }

  const support = [+(price * 0.97).toFixed(2), +(price * 0.94).toFixed(2), +Math.max(low52 * 1.02, price * 0.90).toFixed(2)];
  const resistance = [+(price * 1.03).toFixed(2), +(price * 1.06).toFixed(2), +Math.min(high52 * 0.99, price * 1.10).toFixed(2)];
  const basis = [trendText, rsiText, volText, macdText];

  const data = {
    ok: true,
    symbol,
    name: meta2.name,
    sector: meta2.sector,
    peers: meta2.peers,
    price: +price.toFixed(2),
    change24h: +change24h.toFixed(2),
    rsi,
    ma20: +ma20.toFixed(2),
    ma50: +ma50.toFixed(2),
    ma200: +ma200.toFixed(2),
    trend: trendSimple,
    trendDetail: trend,
    atrPct: +atrPct.toFixed(2),
    momentum5: +momentum5.toFixed(2),
    momentum20: +momentum20.toFixed(2),
    bias,
    confidence: Math.round(confidence),
    risk,
    high52: +high52.toFixed(2),
    low52: +low52.toFixed(2),
    range52Pct: +range52Pct.toFixed(0),
    vol,
    avgVol: +avgVol.toFixed(0),
    volRatio: +volRatio.toFixed(2),
    boll: { upper: +boll.upper.toFixed(2), mid: +boll.mid.toFixed(2), lower: +boll.lower.toFixed(2) },
    bollPct: +bollPct.toFixed(0),
    macd,
    support,
    resistance,
    action,
    basis,
  };
  cache.set(symbol, { ts: Date.now(), data });
  return data;
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const symbol = (searchParams.get("symbol") ?? "NVDA").toUpperCase();
  if (!STOCKS.includes(symbol)) return Response.json({ ok: false, error: "unsupported" }, { status: 400 });
  try {
    const data = await fetchYahoo(symbol);
    return Response.json(data);
  } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
