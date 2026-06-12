export type AssetClass = "crypto" | "stock";
export type Direction = "long" | "short";
export type Tier = "S" | "A" | "B" | "C";
export type EntryGrade = "S" | "A" | "B" | "C" | "D";

export interface Ticker {
  symbol: string; name: string; class: AssetClass;
  price: number; changePct: number; volume: number;
  marketCap?: number; openInterest?: number; longShortRatio?: number; fundingRate?: number;
  spark: number[];
  tvSymbol: string;
}

export interface MarketStats {
  fearGreed: number; btcDominance: number; liq24h: number;
  signalWinRate: number; signalCount: number; ev: number;
}

export interface TakeProfit { level: number; price: number; r: number; weight: number; hit: boolean; }

export interface Signal {
  id: string; symbol: string; direction: Direction;
  tier: Tier; entryGrade: EntryGrade;          // 內部值不翻譯，顯示層才轉中文
  score: number; votes: number; newsVote: -1 | 0 | 1;
  entryLow: number; entryHigh: number; stopLoss: number;
  tps: TakeProfit[];                            // 3 段或 4 段皆相容（陣列）
  leverage: number; winRate: number; rr: number;
  status: "active" | "tp" | "sl" | "closed";
  finalPct?: number; openedAt: string; note?: string;
}

export interface SignalStats {
  n: number; winRate: number; ev: number;
  avgWin: number; avgLoss: number; maxLossStreak: number;
  wilsonLb: number;
}

export interface SignalsResponse {
  source: "live" | "demo" | "error";
  error?: string;
  active: Signal[];
  history: Signal[];
  stats: SignalStats;
}

export interface NewsItem {
  id: string; title: string; source: string; time: string;
  sentiment: "bull" | "bear" | "neutral"; impact: 1 | 2 | 3 | 4 | 5;
  summary: string; tags: string[];
}

export interface AlertItem {
  id: string; type: "whale" | "flow" | "liquidation" | "funding" | "volume";
  severity: "info" | "warn" | "critical";
  title: string; detail: string; time: string; symbol?: string;
}

export interface AnalysisItem {
  symbol: string; bias: "long" | "short" | "neutral";
  confidence: number; risk: number;
  support: number[]; resistance: number[];
  action: string; basis: string[]; sentiment: number;
}
