import { Ticker, Signal, NewsItem, AlertItem, AnalysisItem, MarketStats } from "./types";
import { makeRng } from "./format";

function spark(seed: number, base: number, vol: number, n = 36): number[] {
  const r = makeRng(seed); const out: number[] = []; let p = base;
  for (let i = 0; i < n; i++) { p *= 1 + (r() - 0.48) * vol; out.push(+p.toFixed(6)); }
  return out;
}

export const TICKERS: Ticker[] = [
  { symbol: "BTC", name: "Bitcoin", class: "crypto", price: 96842, changePct: 2.41, volume: 38200000000, openInterest: 21400000000, longShortRatio: 1.08, fundingRate: 0.000082, spark: spark(1, 94800, 0.01), tvSymbol: "BINANCE:BTCUSDT" },
  { symbol: "ETH", name: "Ethereum", class: "crypto", price: 3412.5, changePct: 1.12, volume: 16500000000, openInterest: 9800000000, longShortRatio: 0.96, fundingRate: 0.000051, spark: spark(2, 3380, 0.012), tvSymbol: "BINANCE:ETHUSDT" },
  { symbol: "SOL", name: "Solana", class: "crypto", price: 176.4, changePct: 4.85, volume: 4900000000, openInterest: 2100000000, longShortRatio: 1.21, fundingRate: 0.00012, spark: spark(3, 168, 0.018), tvSymbol: "BINANCE:SOLUSDT" },
  { symbol: "BNB", name: "BNB", class: "crypto", price: 672.3, changePct: -0.64, volume: 1800000000, fundingRate: 0.00003, spark: spark(4, 678, 0.008), tvSymbol: "BINANCE:BNBUSDT" },
  { symbol: "XRP", name: "Ripple", class: "crypto", price: 1.926, changePct: -2.18, volume: 3300000000, fundingRate: -0.00004, spark: spark(5, 1.98, 0.015), tvSymbol: "BINANCE:XRPUSDT" },
  { symbol: "SUI", name: "Sui", class: "crypto", price: 2.842, changePct: 6.3, volume: 1100000000, fundingRate: 0.00018, spark: spark(6, 2.66, 0.022), tvSymbol: "BINANCE:SUIUSDT" },
  { symbol: "DOGE", name: "Dogecoin", class: "crypto", price: 0.1624, changePct: 3.4, volume: 2400000000, fundingRate: 0.00009, spark: spark(7, 0.156, 0.02), tvSymbol: "BINANCE:DOGEUSDT" },
  { symbol: "PEPE", name: "Pepe", class: "crypto", price: 0.0000118, changePct: 8.9, volume: 980000000, fundingRate: 0.00025, spark: spark(8, 0.0000108, 0.03), tvSymbol: "BINANCE:PEPEUSDT" },
  { symbol: "NVDA", name: "NVIDIA", class: "stock", price: 142.6, changePct: 1.86, volume: 18200000000, marketCap: 3500000000000, spark: spark(11, 139.5, 0.008), tvSymbol: "NASDAQ:NVDA" },
  { symbol: "TSLA", name: "Tesla", class: "stock", price: 248.3, changePct: -1.42, volume: 9600000000, marketCap: 790000000000, spark: spark(12, 252, 0.012), tvSymbol: "NASDAQ:TSLA" },
  { symbol: "AAPL", name: "Apple", class: "stock", price: 232.1, changePct: 0.54, volume: 7400000000, marketCap: 3500000000000, spark: spark(13, 230.5, 0.005), tvSymbol: "NASDAQ:AAPL" },
  { symbol: "MSFT", name: "Microsoft", class: "stock", price: 428.9, changePct: 0.92, volume: 6100000000, marketCap: 3180000000000, spark: spark(14, 424, 0.005), tvSymbol: "NASDAQ:MSFT" },
  { symbol: "META", name: "Meta", class: "stock", price: 585.2, changePct: 2.05, volume: 4800000000, marketCap: 1480000000000, spark: spark(15, 573, 0.009), tvSymbol: "NASDAQ:META" },
  { symbol: "AMZN", name: "Amazon", class: "stock", price: 198.7, changePct: 1.18, volume: 5200000000, marketCap: 2080000000000, spark: spark(16, 196, 0.007), tvSymbol: "NASDAQ:AMZN" },
  { symbol: "GOOGL", name: "Alphabet", class: "stock", price: 178.4, changePct: -0.31, volume: 3900000000, marketCap: 2190000000000, spark: spark(17, 179, 0.006), tvSymbol: "NASDAQ:GOOGL" },
  { symbol: "SPY", name: "S&P 500 ETF", class: "stock", price: 595.3, changePct: 0.42, volume: 42000000000, marketCap: 0, spark: spark(18, 592, 0.004), tvSymbol: "AMEX:SPY" },
  { symbol: "QQQ", name: "Nasdaq 100 ETF", class: "stock", price: 512.8, changePct: 0.78, volume: 21000000000, marketCap: 0, spark: spark(19, 508, 0.005), tvSymbol: "NASDAQ:QQQ" },
];

export const MARKET_STATS: MarketStats = {
  fearGreed: 61, btcDominance: 57.8, liq24h: 184000000,
  signalWinRate: 33.3, signalCount: 12, ev: -0.03,
};

export const SIGNALS: Signal[] = [
  {
    id: "sig-001", symbol: "BTC", direction: "long", tier: "S", entryGrade: "A", score: 84, votes: 6, newsVote: 1,
    entryLow: 96200, entryHigh: 96900, stopLoss: 94600, leverage: 5, winRate: 58, rr: 1.5, status: "active", openedAt: "2026-06-13T02:10:00Z",
    tps: [
      { level: 1, price: 99400, r: 1.5, weight: 15, hit: false },
      { level: 2, price: 101600, r: 2.5, weight: 35, hit: false },
      { level: 3, price: 103800, r: 3.5, weight: 35, hit: false },
      { level: 4, price: 107000, r: 5.0, weight: 15, hit: false },
    ],
  },
  {
    id: "sig-002", symbol: "SOL", direction: "long", tier: "A", entryGrade: "B", score: 71, votes: 5, newsVote: 0,
    entryLow: 174.2, entryHigh: 176.8, stopLoss: 168.0, leverage: 3, winRate: 51, rr: 1.5, status: "active", openedAt: "2026-06-13T01:30:00Z",
    tps: [
      { level: 1, price: 184.7, r: 1.5, weight: 15, hit: true },
      { level: 2, price: 190.8, r: 2.5, weight: 35, hit: false },
      { level: 3, price: 196.9, r: 3.5, weight: 35, hit: false },
      { level: 4, price: 205.0, r: 5.0, weight: 15, hit: false },
    ],
  },
  {
    id: "sig-003", symbol: "XRP", direction: "short", tier: "A", entryGrade: "B", score: 66, votes: 4, newsVote: -1,
    entryLow: 1.926, entryHigh: 1.948, stopLoss: 1.992, leverage: 3, winRate: 48, rr: 1.5, status: "active", openedAt: "2026-06-13T00:50:00Z",
    tps: [
      { level: 1, price: 1.871, r: 1.5, weight: 15, hit: false },
      { level: 2, price: 1.808, r: 2.5, weight: 35, hit: false },
      { level: 3, price: 1.745, r: 3.5, weight: 35, hit: false },
      { level: 4, price: 1.660, r: 5.0, weight: 15, hit: false },
    ],
  },
  {
    id: "sig-004", symbol: "DOGE", direction: "long", tier: "A", entryGrade: "B", score: 69, votes: 5, newsVote: 0,
    entryLow: 0.1624, entryHigh: 0.1652, stopLoss: 0.1560, leverage: 4, winRate: 50, rr: 1.5, status: "tp", finalPct: 4.21, openedAt: "2026-06-12T18:20:00Z",
    tps: [
      { level: 1, price: 0.1688, r: 1.5, weight: 15, hit: true },
      { level: 2, price: 0.1745, r: 2.5, weight: 35, hit: true },
      { level: 3, price: 0.1802, r: 3.5, weight: 35, hit: false },
      { level: 4, price: 0.1880, r: 5.0, weight: 15, hit: false },
    ],
  },
  {
    id: "sig-005", symbol: "ETH", direction: "short", tier: "B", entryGrade: "C", score: 58, votes: 3, newsVote: 0,
    entryLow: 3412, entryHigh: 3438, stopLoss: 3502, leverage: 3, winRate: 44, rr: 1.5, status: "sl", finalPct: -2.6, openedAt: "2026-06-12T14:05:00Z",
    tps: [
      { level: 1, price: 3342, r: 1.5, weight: 15, hit: false },
      { level: 2, price: 3253, r: 2.5, weight: 35, hit: false },
      { level: 3, price: 3164, r: 3.5, weight: 35, hit: false },
      { level: 4, price: 3050, r: 5.0, weight: 15, hit: false },
    ],
  },
  {
    id: "sig-006", symbol: "SUI", direction: "long", tier: "C", entryGrade: "D", score: 26, votes: 2, newsVote: 0,
    entryLow: 2.842, entryHigh: 2.880, stopLoss: 2.740, leverage: 2, winRate: 33, rr: 1.5, status: "active", openedAt: "2026-06-13T03:00:00Z", note: "盤整期觀察單，結構偏負期望，僅供參考",
    tps: [
      { level: 1, price: 2.910, r: 1.5, weight: 15, hit: false },
      { level: 2, price: 2.970, r: 2.5, weight: 35, hit: false },
      { level: 3, price: 3.030, r: 3.5, weight: 35, hit: false },
      { level: 4, price: 3.110, r: 5.0, weight: 15, hit: false },
    ],
  },
];

export const NEWS: NewsItem[] = [
  { id: "n1", title: "美國 5 月 CPI 低於市場預期，降息預期升溫", source: "Reuters", time: "08:42", sentiment: "bull", impact: 5, summary: "通膨數據降溫，市場對年內降息押注上升，風險資產普遍走強。", tags: ["BTC", "ETH", "宏觀"] },
  { id: "n2", title: "比特幣現貨 ETF 單日淨流入創近一個月新高", source: "The Block", time: "07:15", sentiment: "bull", impact: 4, summary: "機構資金回流，現貨 ETF 淨流入放大，短線情緒偏多。", tags: ["BTC", "ETF"] },
  { id: "n3", title: "FOMC 利率決議按兵不動，聲明措辭中性", source: "Bloomberg", time: "昨天", sentiment: "neutral", impact: 3, summary: "利率維持不變，點陣圖未明顯偏鷹，市場解讀偏中性。", tags: ["宏觀", "利率"] },
  { id: "n4", title: "某中型交易所傳出熱錢包異常提領，官方稱正在調查", source: "CoinDesk", time: "06:50", sentiment: "bear", impact: 4, summary: "交易所安全事件引發避險情緒，相關代幣短線承壓。", tags: ["風險", "交易所"] },
  { id: "n5", title: "Solana 生態 TVL 創年內新高，DEX 量能放大", source: "CryptoPanic", time: "05:30", sentiment: "bull", impact: 3, summary: "鏈上活躍度提升，生態資金流入，SOL 相對強勢。", tags: ["SOL", "DeFi"] },
  { id: "n6", title: "NVIDIA 財報優於預期，資料中心營收續創新高", source: "Bloomberg", time: "昨天", sentiment: "bull", impact: 4, summary: "AI 需求強勁，帶動科技股與風險偏好。", tags: ["NVDA", "美股"] },
  { id: "n7", title: "鏈上監測：巨鯨地址向交易所轉入大額 ETH", source: "Arkham", time: "03:22", sentiment: "bear", impact: 3, summary: "大額轉入交易所通常被解讀為潛在賣壓。", tags: ["ETH", "鏈上"] },
  { id: "n8", title: "歐盟 MiCA 細則進入下一階段，穩定幣規範趨明確", source: "Reuters", time: "昨天", sentiment: "neutral", impact: 2, summary: "監管框架逐步落地，中長期利於合規參與者。", tags: ["監管", "穩定幣"] },
];

export const ALERTS: AlertItem[] = [
  { id: "a1", type: "liquidation", severity: "critical", title: "BTC 多單 5 分鐘內爆倉 $23.4M", detail: "短時急跌觸發槓桿多單連環清算。", time: "08:55", symbol: "BTC" },
  { id: "a2", type: "whale", severity: "info", title: "巨鯨 2,300 BTC 轉入冷錢包", detail: "由交易所提領至冷錢包，偏中性偏多。", time: "08:30", symbol: "BTC" },
  { id: "a3", type: "flow", severity: "warn", title: "Binance ETH 異常流入 4.2 萬枚", detail: "短時大額流入交易所，留意賣壓。", time: "08:10", symbol: "ETH" },
  { id: "a4", type: "funding", severity: "warn", title: "XRP 資金費率飆升至 0.12%", detail: "多頭擁擠，留意回調風險。", time: "07:48", symbol: "XRP" },
  { id: "a5", type: "volume", severity: "warn", title: "SUI 1 小時成交量達均值 5.2 倍", detail: "量能異常放大，波動加劇。", time: "07:20", symbol: "SUI" },
  { id: "a6", type: "whale", severity: "info", title: "Tether 增發 10 億 USDT（授權未發行）", detail: "授權未發行，屬例行補充流動性。", time: "06:40" },
  { id: "a7", type: "flow", severity: "info", title: "Coinbase BTC 連續 3 日淨流出", detail: "美國機構持續買入跡象。", time: "06:05", symbol: "BTC" },
  { id: "a8", type: "liquidation", severity: "warn", title: "ETH 空單擠壓，1 小時爆倉 $8.7M", detail: "反彈觸發空單清算。", time: "05:30", symbol: "ETH" },
];

const ALERT_POOL: Omit<AlertItem, "id" | "time">[] = [
  { type: "whale", severity: "info", title: "巨鯨地址新增 18,000 SOL 持倉", detail: "由 DEX 分批買入。", symbol: "SOL" },
  { type: "liquidation", severity: "critical", title: "全網 10 分鐘爆倉 $31M", detail: "多空雙爆，波動加劇。" },
  { type: "funding", severity: "warn", title: "DOGE 資金費率轉負", detail: "空頭情緒升溫，費率自高位回落。", symbol: "DOGE" },
  { type: "flow", severity: "warn", title: "OKX BTC 異常流入 1,200 枚", detail: "短時流入量級偏大。", symbol: "BTC" },
  { type: "volume", severity: "info", title: "PEPE 成交量驟增 3.8 倍", detail: "Meme 板塊資金輪動。", symbol: "PEPE" },
  { type: "whale", severity: "warn", title: "沉睡 5 年的地址轉出 900 BTC", detail: "古老籌碼異動，留意。", symbol: "BTC" },
];

export function randomAlert(): AlertItem {
  const p = ALERT_POOL[Math.floor(Math.random() * ALERT_POOL.length)];
  return { ...p, id: "live-" + Date.now() + "-" + Math.floor(Math.random() * 1000), time: new Date().toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" }) };
}

export const ANALYSES: AnalysisItem[] = [
  { symbol: "BTC", bias: "long", confidence: 72, risk: 38, support: [94200, 92800], resistance: [98800, 101500], action: "回踩支撐分批做多，止損置於 92800 下方。", basis: ["趨勢向上", "ETF 資金流入", "結構未破"], sentiment: 64 },
  { symbol: "ETH", bias: "neutral", confidence: 51, risk: 47, support: [3280, 3150], resistance: [3520, 3680], action: "區間操作為主，突破再追。", basis: ["區間震盪", "量能普通"], sentiment: 52 },
  { symbol: "SOL", bias: "long", confidence: 68, risk: 52, support: [168.5, 161.0], resistance: [184.7, 196.0], action: "強勢回踩做多，嚴設止損。", basis: ["生態 TVL 創高", "相對強勢"], sentiment: 66 },
  { symbol: "NVDA", bias: "long", confidence: 70, risk: 35, support: [136.0, 128.5], resistance: [148.0, 156.0], action: "AI 需求支撐，回調布局。", basis: ["財報優於預期", "趨勢健康"], sentiment: 68 },
  { symbol: "TSLA", bias: "short", confidence: 56, risk: 61, support: [232.0, 218.0], resistance: [256.0, 270.0], action: "反彈至阻力區偏空操作。", basis: ["動能轉弱", "高波動"], sentiment: 42 },
];
