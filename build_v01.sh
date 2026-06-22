#!/usr/bin/env bash
# ============================================================
# 黑潮 BLACKTIDE — Web Dashboard v0.1（完整單檔版）
# 在 repo 根目錄執行（需已 rm -rf 舊的 blacktide-web）
# ============================================================
set -e
mkdir -p blacktide-web/app/api/market blacktide-web/app/api/signals blacktide-web/app/api/news blacktide-web/app/api/alerts
mkdir -p blacktide-web/app/signals blacktide-web/app/analysis blacktide-web/app/news blacktide-web/app/monitor blacktide-web/app/backtest
mkdir -p blacktide-web/components blacktide-web/lib
cd blacktide-web

cat > package.json <<'BTEOF'
{
  "name": "blacktide-web",
  "version": "0.1.0",
  "private": true,
  "scripts": { "dev": "next dev", "build": "next build", "start": "next start" },
  "dependencies": {
    "framer-motion": "^11.11.17",
    "lucide-react": "^0.453.0",
    "next": "14.2.21",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "zustand": "^4.5.5"
  },
  "devDependencies": {
    "@types/node": "^20.17.6",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.15",
    "typescript": "^5.6.3"
  }
}
BTEOF

cat > tsconfig.json <<'BTEOF'
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true, "skipLibCheck": true, "strict": true, "noEmit": true,
    "esModuleInterop": true, "module": "esnext", "moduleResolution": "bundler",
    "resolveJsonModule": true, "isolatedModules": true, "jsx": "preserve", "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
BTEOF

cat > next-env.d.ts <<'BTEOF'
/// <reference types="next" />
/// <reference types="next/image-types/global" />
BTEOF

cat > next.config.mjs <<'BTEOF'
/** @type {import('next').NextConfig} */
const nextConfig = { reactStrictMode: true };
export default nextConfig;
BTEOF

cat > postcss.config.js <<'BTEOF'
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };
BTEOF

cat > tailwind.config.ts <<'BTEOF'
import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#070b12", 900: "#0a0f18", 800: "#0e1521", 700: "#131c2b", 600: "#1a2436" },
        tide: { 300: "#67e8f9", 400: "#22d3ee", 500: "#06b6d4", 600: "#0891b2" },
        up: "#10b981", down: "#f43f5e"
      },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] }
    }
  },
  plugins: []
};
export default config;
BTEOF

cat > .gitignore <<'BTEOF'
node_modules
.next
out
.env
.env*.local
.DS_Store
BTEOF

cat > .env.example <<'BTEOF'
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
BOT_REDIS_KEY=bot_data
BTEOF

cat > app/globals.css <<'BTEOF'
@tailwind base;
@tailwind components;
@tailwind utilities;

:root { color-scheme: dark; }
html, body { height: 100%; }
body { background: #070b12; color: #e2e8f0; font-feature-settings: "tnum" 1; }
::selection { background: rgba(34, 211, 238, 0.25); }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #1a2436; border-radius: 8px; }
::-webkit-scrollbar-track { background: transparent; }

.flash-up { animation: flashUp 0.6s ease-out; }
.flash-down { animation: flashDown 0.6s ease-out; }
@keyframes flashUp { 0% { color: #10b981; } 100% { color: inherit; } }
@keyframes flashDown { 0% { color: #f43f5e; } 100% { color: inherit; } }
.pulse-dot { animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
BTEOF

cat > lib/types.ts <<'BTEOF'
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
export interface MarketStats {
  fearGreed: number; btcDominance: number; liq24h: number;
  signalWinRate: number; signalCount: number; ev: number;
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
BTEOF

cat > lib/format.ts <<'BTEOF'
export function fmtPrice(p: number): string {
  if (!isFinite(p)) return "-";
  if (p >= 1000) return p.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (p >= 1) return p.toFixed(2);
  if (p >= 0.01) return p.toFixed(4);
  return p.toPrecision(3);
}
export function fmtPct(x: number): string { return `${x >= 0 ? "+" : ""}${x.toFixed(2)}%`; }
export function compactZh(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e8) return (n / 1e8).toFixed(2) + "億";
  if (abs >= 1e4) return (n / 1e4).toFixed(0) + "萬";
  return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}
export function entryGradeDisplay(g: string): string {
  if (g === "S" || g === "A") return "高品質";
  if (g === "B" || g === "C") return "一般品質";
  return "低品質";
}
export function makeRng(seed: number) {
  return function () {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
BTEOF

cat > lib/mock.ts <<'BTEOF'
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
  { symbol: "SPY", name: "S&P 500 ETF", class:

