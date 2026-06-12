import {
  Ticker, Signal, NewsItem, AlertItem, AnalysisItem, MarketStats, SignalStats,
} from "./types";
import { makeRng } from "./format";

function spark(seed: number, base: number, vol: number, n = 36): number[] {
  const r = makeRng(seed);
  const out: number[] = [];
  let p = base;
  for (let i = 0; i < n; i++) {
    p *= 1 + (r() - 0.48) * vol;
    out.push(+p.toFixed(6));
  }
  return out;
}

export const TICKERS: Ticker[] = [
  { symbol: "BTC", name: "Bitcoin", class: "crypto", price: 96842, changePct: 2.41, volume: 38_200_000_000, openInterest: 21_400_000_000, longShortRatio: 1.08, fundingRate: 0.000082, spark: spark(1, 94800, 0.01), tvSymbol: "BINANCE:BTCUSDT" },
  { symbol: "ETH", name: "Ethereum", class: "crypto", price: 3412.5, changePct: 1.12, volume: 16_500_000_000, openInterest: 9_800_000_000, longShortRatio: 0.96, fundingRate: 0.000051, spark: spark(2, 3380, 0.012), tvSymbol: "BINANCE:ETHUSDT" },
  { symbol: "SOL", name: "Solana", class: "crypto", price: 176.4, changePct: 4.85, volume: 4_900_000_000, openInterest: 2_100_000_000, longShortRatio: 1.21, fundingRate: 0.00012, spark: spark(3, 168, 0.018), tvSymbol: "BINANCE:SOLUSDT" },
  { symbol: "BNB", name: "BNB", class: "crypto", price: 672.3, changePct: -0.64, volume: 1_800_000_000, fundingRate: 0.00003, spark: spark(4, 678, 0.008), tvSymbol: "BINANCE:BNBUSDT" },
  { symbol: "XRP", name: "Ripple", class: "crypto", price: 1.926, changePct: -2.18, volume: 3_300_000_000, fundingRate: -0.00004, spark: spark(5, 1.98, 0.015), tvSymbol: "BINANCE:XRPUSDT" },
  { symbol: "SUI", name: "Sui", class: "crypto", price: 2.842, changePct: 6.3, volume: 1_100_000_000, fundingRate: 0.00018, spark: spark(6, 2.66, 0.022), tvSymbol: "BINANCE:SUIUSDT" },
  { symbol: "DOGE", name: "Dogecoin", class: "crypto", price: 0.1624, changePct: 3.4, volume: 2_400_000_000, fundingRate: 0.00009, spark: spark(7, 0.156, 0.02), tvSymbol: "BINANCE:DOGEUSDT" },
  { symbol: "PEPE", name: "Pepe", class: "crypto", price: 0.0000118, changePct: 8.9, volume: 980_000_000, fundingRate: 0.00025, spark: spark(8, 0.0000108, 0.03), tvSymbol: "BINANCE:PEPEUSDT" },
  { symbol: "NVDA", name: "NVIDIA", class: "stock", price: 142.6, changePct: 1.86, volume: 18_200_000_000, marketCap: 3_500_000_000_000, spark: spark(11, 139.5, 0.008), tvSymbol: "NASDAQ:NVDA" },
  { symbol: "TSLA", name: "Tesla", class: "stock", price: 248.3, changePct: -1.42, volume: 9_600_000_000, marketCap: 790_000_000_000, spark: spark(12, 252, 0.012), tvSymbol: "NASDAQ:TSLA" },
  { symbol: "AAPL", name: "Apple", class: "stock", price: 232.1, changePct: 0.54, volume: 7_400_000_000, marketCap: 3_500_000_000_000, spark: spark(13, 230.8, 0.006), tvSymbol: "NASDAQ:AAPL" },
  { symbol: "COIN", name: "Coinbase", class: "stock", price: 312.7, changePct: 3.95, volume: 2_100_000_000, marketCap: 78_000_000_000, spark: spark(14, 300, 0.014), tvSymbol: "NASDAQ:COIN" },
];

export const MARKET_STATS: MarketStats = {
  fearGreed: 64,
  btcDominance: 56.8,
  liq24h: 184_000_000,
  signalWinRate: 41.7,
  signalCount: 24,
  ev: 0.28,
};

function tp(level: number, price: number, r: number, weight: number, hit: boolean) {
  return { level, price, r, weight, hit };
}

export const DEMO_SIGNALS: Signal[] = [
  {
    id: "BTC/USDT_LONG", symbol: "BTC", direction: "long", tier: "A", entryGrade: "A",
    score: 78, votes: 5, newsVote: 1,
    entryLow: 96200, entryHigh: 96200, stopLoss: 94100,
    tps: [tp(1, 97200, 1.5, 15, true), tp(2, 98700, 2.5, 35, false), tp(3, 100200, 3.5, 35, false), tp(4, 102800, 5.0, 15, false)],
    leverage: 15, winRate: 47, rr: 1.9, status: "tp", openedAt: new Date(Date.now() - 3600_000 * 4).toISOString(),
  },
  {
    id: "SOL/USDT_LONG", symbol: "SOL", direction: "long", tier: "S", entryGrade: "S",
    score: 86, votes: 6, newsVote: 1,
    entryLow: 172.5, entryHigh: 172.5, stopLoss: 166.0,
    tps: [tp(1, 176.5, 1.5, 15, false), tp(2, 181.0, 2.5, 35, false), tp(3, 185.5, 3.5, 35, false), tp(4, 192.0, 5.0, 15, false)],
    leverage: 15, winRate: 52, rr: 2.3, status: "active", openedAt: new Date(Date.now() - 3600_000 * 1.2).toISOString(),
  },
  {
    id: "XRP/USDT_SHORT", symbol: "XRP", direction: "short", tier: "B", entryGrade: "C",
    score: 61, votes: 3, newsVote: 0,
    entryLow: 1.962, entryHigh: 1.962, stopLoss: 2.012,
    tps: [tp(1, 1.93, 1.5, 15, true), tp(2, 1.895, 2.5, 35, true), tp(3, 1.86, 3.5, 35, false), tp(4, 1.81, 5.0, 15, false)],
    leverage: 15, winRate: 44, rr: 1.7, status: "tp", openedAt: new Date(Date.now() - 3600_000 * 9).toISOString(),
  },
  {
    id: "SUI/USDT_LONG", symbol: "SUI", direction: "long", tier: "C", entryGrade: "B",
    score: 58, votes: 3, newsVote: 0,
    entryLow: 2.74, entryHigh: 2.74, stopLoss: 2.61,
    tps: [tp(1, 2.83, 1.5, 15, false), tp(2, 2.95, 2.5, 35, false), tp(3, 3.07, 3.5, 35, false), tp(4, 3.25, 5.0, 15, false)],
    leverage: 15, winRate: 39, rr: 1.6, status: "active", openedAt: new Date(Date.now() - 3600_000 * 0.4).toISOString(),
  },
];

export const DEMO_HISTORY: Signal[] = [
  { id: "h1", symbol: "ETH", direction: "long", tier: "A", entryGrade: "A", score: 74, votes: 5, newsVote: 1, entryLow: 3360, entryHigh: 3360, stopLoss: 3280, tps: [], leverage: 15, winRate: 0, rr: 1.9, status: "closed", finalPct: 4.62, openedAt: new Date(Date.now() - 86400_000 * 1).toISOString(), note: "TP3_HIT" },
  { id: "h2", symbol: "DOGE", direction: "long", tier: "B", entryGrade: "C", score: 55, votes: 3, newsVote: 0, entryLow: 0.158, entryHigh: 0.158, stopLoss: 0.152, tps: [], leverage: 15, winRate: 0, rr: 1.5, status: "closed", finalPct: -2.81, openedAt: new Date(Date.now() - 86400_000 * 1.5).toISOString(), note: "SL_HIT" },
  { id: "h3", symbol: "BNB", direction: "short", tier: "C", entryGrade: "C", score: 52, votes: 2, newsVote: 0, entryLow: 686, entryHigh: 686, stopLoss: 699, tps: [], leverage: 15, winRate: 0, rr: 1.6, status: "closed", finalPct: -3.04, openedAt: new Date(Date.now() - 86400_000 * 2).toISOString(), note: "SL_HIT" },
  { id: "h4", symbol: "SOL", direction: "long", tier: "S", entryGrade: "S", score: 88, votes: 6, newsVote: 1, entryLow: 162, entryHigh: 162, stopLoss: 156, tps: [], leverage: 15, winRate: 0, rr: 2.4, status: "closed", finalPct: 8.83, openedAt: new Date(Date.now() - 86400_000 * 2.4).toISOString(), note: "TP4_HIT" },
  { id: "h5", symbol: "XRP", direction: "short", tier: "A", entryGrade: "A", score: 71, votes: 4, newsVote: -1, entryLow: 2.05, entryHigh: 2.05, stopLoss: 2.11, tps: [], leverage: 15, winRate: 0, rr: 1.8, status: "closed", finalPct: 5.21, openedAt: new Date(Date.now() - 86400_000 * 3).toISOString(), note: "TP2_HIT" },
  { id: "h6", symbol: "PEPE", direction: "long", tier: "C", entryGrade: "D", score: 31, votes: 2, newsVote: 0, entryLow: 0.0000108, entryHigh: 0.0000108, stopLoss: 0.0000102, tps: [], leverage: 15, winRate: 0, rr: 1.4, status: "closed", finalPct: -4.12, openedAt: new Date(Date.now() - 86400_000 * 3.6).toISOString(), note: "SL_HIT" },
  { id: "h7", symbol: "BTC", direction: "long", tier: "A", entryGrade: "B", score: 69, votes: 4, newsVote: 1, entryLow: 92000, entryHigh: 92000, stopLoss: 90100, tps: [], leverage: 15, winRate: 0, rr: 1.9, status: "closed", finalPct: 3.18, openedAt: new Date(Date.now() - 86400_000 * 4).toISOString(), note: "TP2_HIT" },
  { id: "h8", symbol: "SUI", direction: "long", tier: "B", entryGrade: "C", score: 54, votes: 3, newsVote: 0, entryLow: 2.5, entryHigh: 2.5, stopLoss: 2.38, tps: [], leverage: 15, winRate: 0, rr: 1.6, status: "closed", finalPct: -2.55, openedAt: new Date(Date.now() - 86400_000 * 5).toISOString(), note: "SL_HIT" },
];

export const DEMO_STATS: SignalStats = {
  n: DEMO_HISTORY.length,
  winRate: (DEMO_HISTORY.filter((s) => (s.finalPct ?? 0) > 0).length / DEMO_HISTORY.length) * 100,
  ev: DEMO_HISTORY.reduce((a, s) => a + (s.finalPct ?? 0), 0) / DEMO_HISTORY.length,
  avgWin: 5.0,
  avgLoss: -3.13,
  maxLossStreak: 2,
  wilsonLb: 18.4,
};

export const NEWS: NewsItem[] = [
  { id: "n1", title: "美國 CPI 低於預期，風險資產普遍走高", source: "Reuters", time: new Date(Date.now() - 1800_000).toISOString(), sentiment: "bull", impact: 5, summary: "通膨數據放緩，市場押注降息提前，BTC 重新站上 96k。", tags: ["宏觀", "BTC", "降息"] },
  { id: "n2", title: "某交易所傳大額 BTC 流出至冷錢包", source: "Whale Alert", time: new Date(Date.now() - 5400_000).toISOString(), sentiment: "bull", impact: 3, summary: "12,400 BTC 自熱錢包轉出，通常解讀為惜售訊號。", tags: ["鏈上", "BTC"] },
  { id: "n3", title: "SEC 對某 DeFi 協議展開調查", source: "Bloomberg", time: new Date(Date.now() - 9000_000).toISOString(), sentiment: "bear", impact: 4, summary: "監管不確定性升溫，相關代幣短線承壓。", tags: ["監管", "DeFi"] },
  { id: "n4", title: "以太坊基金會公布下一階段擴容路線圖", source: "The Block", time: new Date(Date.now() - 14400_000).toISOString(), sentiment: "neutral", impact: 2, summary: "技術面進展，短期價格影響有限。", tags: ["ETH", "技術"] },
];

export const ALERTS: AlertItem[] = [
  { id: "a1", type: "whale", severity: "warn", title: "巨鯨買入 SOL", detail: "單筆 420 萬 USD 市價買入，OI 同步上升。", time: new Date(Date.now() - 600_000).toISOString(), symbol: "SOL" },
  { id: "a2", type: "liquidation", severity: "critical", title: "BTC 多單連環爆倉", detail: "近 1 小時多單爆倉 5,800 萬 USD。", time: new Date(Date.now() - 1500_000).toISOString(), symbol: "BTC" },
  { id: "a3", type: "funding", severity: "info", title: "PEPE 資金費率轉正偏高", detail: "費率 +0.025%，多頭情緒擁擠，留意回調。", time: new Date(Date.now() - 3000_000).toISOString(), symbol: "PEPE" },
  { id: "a4", type: "volume", severity: "warn", title: "SUI 異常放量", detail: "15m 成交量為均量 3.2 倍，伴隨價格突破。", time: new Date(Date.now() - 4200_000).toISOString(), symbol: "SUI" },
];

export const ANALYSIS: AnalysisItem[] = [
  { symbol: "BTC", bias: "long", confidence: 72, risk: 38, support: [94000, 92500, 90000], resistance: [98000, 100000, 103500], action: "回踩 94k 不破可分批做多，止損 92.5k", basis: ["7+1 策略 5 票看多", "ADX 走強趨勢成立", "資金費率溫和未過熱"], sentiment: 64 },
  { symbol: "SOL", bias: "long", confidence: 81, risk: 44, support: [168, 162, 155], resistance: [181, 188, 196], action: "強勢續多，破 181 加倉，止損 166", basis: ["五維評分 86", "OI 上升量價齊揚", "新聞情緒看多 +1 票"], sentiment: 71 },
  { symbol: "XRP", bias: "short", confidence: 58, risk: 52, support: [1.86, 1.81, 1.75], resistance: [1.98, 2.05, 2.12], action: "反彈至 1.98 偏空，止損 2.02", basis: ["跌破上升趨勢線", "量價齊跌成立", "結構轉弱 BOS 向下"], sentiment: 38 },
  { symbol: "ETH", bias: "neutral", confidence: 49, risk: 41, support: [3280, 3200, 3100], resistance: [3480, 3560, 3680], action: "區間整理，邊緣反轉操作，不追中", basis: ["策略票分歧（3 多 3 空）", "盤整期情境閘門生效", "等待突破確認"], sentiment: 50 },
];
