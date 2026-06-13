"use client";
import { useState } from "react";
import Link from "next/link";
import { Anchor, ChevronRight } from "lucide-react";
import { useMarket } from "@/lib/useMarket";
import { useApp } from "@/lib/store";
import { coinBySymbol } from "@/lib/bybit";
import PriceCard from "@/components/PriceCard";
import CandleChart from "@/components/CandleChart";
import TickerTape from "@/components/TickerTape";
import { Stat, Chip, Card, Badge } from "@/components/ui";
import { fmtPrice, fmtPct, compactZh } from "@/lib/format";
function FearGauge({ v }: { v: number }) {
  const len = Math.PI * 34;
  const pct = Math.max(0, Math.min(100, v)) / 100;
  const color = v < 45 ? "#f43f5e" : v > 55 ? "#10b981" : "#d4af37";
  return (
    <svg viewBox="0 0 80 46" className="w-[72px] shrink-0">
      <path d="M6 42 A34 34 0 0 1 74 42" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" strokeLinecap="round" />
      <path d="M6 42 A34 34 0 0 1 74 42" fill="none" stroke={color} strokeWidth="7" strokeLinecap="round"
        strokeDasharray={`${len * pct} ${len}`} />
      <text x="40" y="40" textAnchor="middle" fill={color} fontSize="15" fontWeight="700" fontFamily="ui-monospace">{v}</text>
    </svg>
  );
}
function Skeleton() {
  return <div className="space-y-4">{[0, 1, 2].map((i) => <div key={i} className="h-28 animate-pulse rounded-xl bg-white/5" />)}</div>;
}
export default function Dashboard() {
  const { tickers, stats, src } = useMarket();
  const { selectedSymbol, watchlist, setSymbol } = useApp();
  const [cls, setCls] = useState<"crypto" | "stock">("crypto");
  if (!tickers.length || !stats) return <Skeleton />;
  const crypto = tickers.filter((t) => t.class === "crypto");
  const sel = tickers.find((t) => t.symbol === selectedSymbol) ?? tickers[0];
  const coin = sel.class === "crypto" ? coinBySymbol(sel.symbol) : undefined;
  const list = tickers.filter((t) => t.class === cls);
  const watched = tickers.filter((t) => watchlist.includes(t.symbol));
  const fgLabel = stats.fearGreed > 55 ? "貪婪" : stats.fearGreed < 45 ? "恐懼" : "中性";
  return (
    <div className="space-y-4 md:space-y-5">
      <TickerTape tickers={crypto} />
      <div className="grid grid-cols-2 gap-2.5 md:gap-3 lg:grid-cols-4">
        <Card className="flex items-center gap-3 p-3.5">
          <FearGauge v={stats.fearGreed} />
          <div className="min-w-0">
            <div className="text-xs text-slate-500">恐懼貪婪指數</div>
            <div className="mt-0.5 text-sm font-semibold">{fgLabel}</div>
          </div>
        </Card>
        <Stat label="BTC 市佔率" value={stats.btcDominance ? stats.btcDominance + "%" : "-"} sub="BTC.D" />
        <Stat label="BTC 24h 成交額" value={stats.btcTurnover ? "$" + compactZh(stats.btcTurnover) : "-"} sub="Bybit 永續" />
        <Stat label="BTC 資金費率" value={stats.btcFunding !== undefined ? (stats.btcFunding * 100).toFixed(4) + "%" : "-"} sub="當期" />
      </div>
      <div>
        <div className="scrollbar-none mb-2.5 flex items-center gap-2 overflow-x-auto">
          <Chip active={cls === "crypto"} onClick={() => setCls("crypto")}>加密貨幣</Chip>
          <Chip active={cls === "stock"} onClick={() => setCls("stock")}>美股</Chip>
          <span className="ml-auto shrink-0">
            {cls === "crypto"
              ? (src.crypto === "bybit" ? <Badge tone="up">Bybit 即時</Badge> : <Badge tone="amber">模擬</Badge>)
              : (src.stocks === "finnhub" ? <Badge tone="up">Finnhub 報價</Badge> : <Badge tone="slate">展示</Badge>)}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2.5 md:gap-3 lg:grid-cols-3 xl:grid-cols-4">
          {list.map((t) => <PriceCard key={t.symbol} t={t} />)}
        </div>
      </div>
      <Link href="/signals" className="group relative block overflow-hidden rounded-2xl">
        <div className="absolute inset-0 rounded-2xl border border-tide-500/30 bg-gradient-to-r from-tide-500/10 via-amber-500/5 to-transparent" />
        <div className="relative flex items-center gap-3 px-4 py-4 md:gap-4 md:px-6">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-tide-500/30 bg-tide-500/10 text-tide-300">
            <Anchor size={22} />
          </span>
          <div className="min-w-0">
            <div className="font-display text-[15px] font-bold tracking-wide text-gold md:text-base">黑潮船長 · 即時訊號中心</div>
            <div className="mt-0.5 truncate text-xs text-slate-400">7+1 策略投票 · 分批止盈計畫 · 績效統計</div>
          </div>
          <ChevronRight className="ml-auto shrink-0 text-tide-300/70 transition-transform group-hover:translate-x-1" size={18} />
        </div>
      </Link>
      <div className="grid gap-4 md:gap-5 xl:grid-cols-3">
        <Card className="p-3 xl:col-span-2">
          <div className="mb-2 flex items-center justify-between px-1">
            <div className="text-sm font-semibold">{sel.symbol} · {sel.name}</div>
            <div className="font-mono text-sm">
              ${fmtPrice(sel.price)}
              <span className={`ml-2 text-xs ${sel.changePct >= 0 ? "text-up" : "text-down"}`}>{fmtPct(sel.changePct)}</span>
            </div>
          </div>
          {coin ? (
            <CandleChart bybitSymbol={coin.bybit} livePrice={sel.price} />
          ) : (
            <div className="flex h-[300px] items-center justify-center rounded-lg border border-white/5 text-center text-xs text-slate-500">
              美股 K 線需行情金鑰（Phase 2）。<br />請選擇加密貨幣查看即時 K 線。
            </div>
          )}
        </Card>
        <Card className="p-4">
          <div className="mb-3 text-sm font-semibold">我的觀察清單</div>
          {watched.length === 0 && <div className="text-xs text-slate-500">點價格卡片右上角的 ★ 加入觀察。</div>}
          <div className="space-y-1.5">
            {watched.map((t) => (
              <button key={t.symbol} onClick={() => setSymbol(t.symbol)}
                className="flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-white/5">
                <span className="font-medium">{t.symbol}</span>
                <span className="ml-auto font-mono text-xs">${fmtPrice(t.price)}</span>
                <span className={`w-16 text-right text-xs ${t.changePct >= 0 ? "text-up" : "text-down"}`}>{fmtPct(t.changePct)}</span>
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
