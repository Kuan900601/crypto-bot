export type AssetClass = "crypto" | "stock";
export type Direction = "long" | "short";
export type Tier = "S" | "A" | "B" | "C";
export type EntryGrade = "S" | "A" | "B" | "C" | "D";
export interface Ticker {
  symbol: string; name: string; class: AssetClass;
  price: number; changePct: number; volume: number;
  marketCap?: number; openInterest?: number; longShortRatio?: number; fundingRate?: number;
  spark: number[]; tvSymbol: string;
}
export interface SymbolLite {
  symbol: string; name: string; type: AssetClass;
  tvSymbol: string; bybit?: string | null;
}
export interface MarketStats {
  fearGreed: number; btcDominance: number;
  btcTurnover?: number; btcFunding?: number;
  liq24h?: number; signalWinRate?: number; signalCount?: number; ev?: number;
}
export interface TakeProfit { level: number; price: number; r: number; weight: number; hit: boolean; }
export interface Signal {
  id: string; symbol: string; direction: Direction;
  tier: Tier; entryGrade: EntryGrade;
  score: number; votes: number; newsVote: -1 | 0 | 1;
  entryLow: number; entryHigh: number; stopLoss: number;
  tps: TakeProfit[];
  leverage: number; winRate: number; rr: number;
  status: "active" | "tp" | "sl" | "closed";
  finalPct?: number; openedAt: string; note?: string;
}
export interface NewsItem {
  id: string; title: string; source: string; time: string;
  sentiment: "bull" | "bear" | "neutral"; impact: 1 | 2 | 3 | 4 | 5;
  summary: string; tags: string[]; url?: string;
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
