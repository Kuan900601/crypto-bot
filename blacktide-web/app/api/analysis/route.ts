import { BYBIT_REST } from "@/lib/bybit";
export const dynamic = "force-dynamic";
const COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE"];
let cache: { ts: number; body: unknown } | null = null;
function sma(a: number[], n: number) { if (a.length < n) return a[a.length - 1] ?? 0; const s = a.slice(a.length - n); return s.reduce((x, y) => x + y, 0) / n; }
function rsi(closes: number[], n = 14) {
  if (closes.length < n + 1) return 50;
  let g = 0, l = 0;
  for (let i = closes.length - n; i < closes.length; i++) { const d = closes[i] - closes[i - 1]; if (d >= 0) g += d; else l -= d; }
  if (l === 0) return 100; const rs = g / l; return 100 - 100 / (1 + rs);
}
function atrPct(h: number[], lo: number[], c: number[], n = 14) {
  if (c.length < n + 1) return 0; const tr: number[] = [];
  for (let i = c.length - n; i < c.length; i++) tr.push(Math.max(h[i] - lo[i], Math.abs(h[i] - c[i - 1]), Math.abs(lo[i] - c[i - 1])));
  const a = tr.reduce((x, y) => x + y, 0) / tr.length; return (a / c[c.length - 1]) * 100;
}
function rnd(v: number) { return v >= 100 ? Math.round(v) : v >= 1 ? +v.toFixed(2) : +v.toPrecision(3); }
function clamp(v: number, lo = 0, hi = 100) { return Math.max(lo, Math.min(hi, Math.round(v))); }
async function analyze(coin: string) {
  const sym = coin + "USDT";
  try {
    const [kr, tr] = await Promise.all([
      fetch(`${BYBIT_REST}/v5/market/kline?category=linear&symbol=${sym}&interval=60&limit=200`, { cache: "no-store" }),
      fetch(`${BYBIT_REST}/v5/market/tickers?category=linear&symbol=${sym}`, { cache: "no-store" }),
    ]);
    const kd = await kr.json();
    const rows = (kd?.result?.list || []) as string[][];
    if (rows.length < 60) return null;
    const k = rows.slice().reverse();
    const closes = k.map((x) => +x[4]), highs = k.map((x) => +x[2]), lows = k.map((x) => +x[3]);
    const price = closes[closes.length - 1];
    const ma20 = sma(closes, 20), ma50 = sma(closes, 50);
    const r = rsi(closes, 14), atr = atrPct(highs, lows, closes, 14);
    const base24 = closes[closes.length - 25] ?? closes[0];
    const mom = ((price - base24) / base24) * 100;
    const td = await tr.json();
    const t = td?.result?.list?.[0] || {};
    const fund = t.fundingRate ? +t.fundingRate * 100 : 0;
    const chg = t.price24hPcnt ? +t.price24hPcnt * 100 : mom;
    const sup = [Math.min(...lows.slice(-20)), Math.min(...lows.slice(-50))].map(rnd);
    const res = [Math.max(...highs.slice(-20)), Math.max(...highs.slice(-50))].map(rnd);
    let bs = 0;
    bs += price > ma20 ? 1 : -1;
    bs += ma20 > ma50 ? 1 : -1;
    bs += mom > 0 ? 1 : -1;
    bs += r > 55 ? 1 : r < 45 ? -1 : 0;
    const trend = price > ma20 && ma20 > ma50 ? "up" : price < ma20 && ma20 < ma50 ? "down" : "side";
    const bias = bs >= 2 ? "long" : bs <= -2 ? "short" : "neutral";
    const confidence = clamp(46 + Math.abs(bs) * 9 + Math.min(14, Math.abs(r - 50) / 2));
    const risk = clamp(30 + atr * 9 + (r >= 72 || r <= 28 ? 18 : 0) + (Math.abs(fund) >= 0.05 ? 10 : 0));
    const sentiment = clamp((r - 50) * 0.8 + 50 + Math.max(-15, Math.min(15, mom)));
    const basis = [
      "趨勢：" + (trend === "up" ? "多頭排列（價 > MA20 > MA50）" : trend === "down" ? "空頭排列（價 < MA20 < MA50）" : "均線糾結，方向不明"),
      "RSI(14) = " + Math.round(r) + "（" + (r > 70 ? "超買，留意回調" : r < 30 ? "超賣，留意反彈" : "中性區間") + "）",
      "近 24 小時動能 " + (mom >= 0 ? "+" : "") + mom.toFixed(1) + "%",
      "波動 ATR ≈ " + atr.toFixed(2) + "%（" + (atr > 3 ? "偏高，控好倉位" : "正常") + "）",
      "資金費率 " + fund.toFixed(4) + "%（" + (Math.abs(fund) >= 0.05 ? "偏離常態，留意擠壓" : "正常") + "）",
    ];
    const action = bias === "long"
      ? "傾向偏多：回踩 " + sup[0] + " 上方、RSI 守住 50 可順勢進場；跌破 " + sup[1] + " 結構轉弱即離場。"
      : bias === "short"
      ? "傾向偏空：反彈至 " + res[0] + " 附近、RSI 站不回 50 可試空；站回 " + res[1] + " 之上停損。"
      : "區間整理：" + sup[0] + " – " + res[0] + " 之間不追單，等帶量突破方向再進場。";
    return {
      symbol: coin, price: rnd(price), change24h: +chg.toFixed(2), rsi: Math.round(r), ma20: rnd(ma20), ma50: rnd(ma50),
      atrPct: +atr.toFixed(2), momentum: +mom.toFixed(1), fundingPct: +fund.toFixed(4), trend, bias,
      confidence, risk, sentiment, support: sup, resistance: res, basis, action,
    };
  } catch { return null; }
}
export async function GET() {
  if (cache && Date.now() - cache.ts < 60000) return Response.json(cache.body);
  const out = (await Promise.all(COINS.map(analyze))).filter(Boolean);
  const body = { analyses: out, source: out.length ? "bybit" : "none", ts: Date.now() };
  if (out.length) cache = { ts: Date.now(), body };
  return Response.json(body);
}
