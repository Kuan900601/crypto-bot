"use client";
import Link from "next/link";
import { TrendingUp, Shield, Brain, Activity, ArrowRight, Crown, Layers, Gauge } from "lucide-react";
import { useMarket } from "@/lib/useMarket";
import { useApp } from "@/lib/store";
import { Card, SectionTitle, Badge } from "@/components/ui";
import { fmtPrice, fmtPct } from "@/lib/format";
import TickerTape from "@/components/TickerTape";
import FearGauge from "@/components/FearGauge";
import PriceCard from "@/components/PriceCard";
import CandleChart from "@/components/CandleChart";
const STRATS = ["趨勢追隨", "動量", "量價", "均線排列", "支撐阻力", "BOS 突破", "訂單流", "新聞情緒"];
const STRENGTHS = [
  { icon: Activity, t: "即時 Bybit 行情", d: "全永續合約即時報價、資金費率、未平倉" },
  { icon: Layers, t: "三段止盈 40/35/25", d: "對齊實際成交，分批鎖利不貪心" },
  { icon: Shield, t: "波動自適應止損", d: "依 ATR 動態調整，達 TP 自動上移保本" },
  { icon: Gauge, t: "五維評分 + Kelly 倉位", d: "趨勢/動能/結構/量能/風險，倉位按品質縮放" },
  { icon: Brain, t: "7+1 策略投票", d: "七技術指標 + 新聞情緒，至少兩票才出手" },
  { icon: TrendingUp, t: "保護模式 / 大盤閘門", d: "連敗降檔、BTC 無趨勢高波動時暫停" },
];
export default function Home() {
  const { tickers, stats } = useMarket();
  const list = tickers;
  const { selectedSymbol, setSymbol, watchlist, setPricingOpen } = useApp();
  const crypto = list.filter((t) => t.class === "crypto");
  const stocks = list.filter((t) => t.class === "stock");
  const watched = list.filter((t) => watchlist.includes(t.symbol));
  return (
    <div className="space-y-6">
      <TickerTape tickers={list} />
      {/* ===== 黑潮船長招牌卡 ===== */}
      <section className="relative overflow-hidden rounded-2xl border border-tide-500/25 p-5 sm:p-6"
        style={{ background: "linear-gradient(135deg, rgba(212,175,55,0.10), rgba(10,12,18,0.4))" }}>
        <div className="pointer-events-none absolute -right-10 -top-10 h-48 w-48 rounded-full bg-tide-500/10 blur-3xl" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center">
          <div className="flex-1">
            <div className="mb-2 flex items-center gap-2">
              <Crown size={18} className="text-tide-300" />
              <span className="font-display text-xs font-semibold uppercase tracking-widest text-tide-300">BlackTide Captain</span>
            </div>
            <h1 className="font-display text-2xl font-bold text-gold glow-gold sm:text-3xl">黑潮船長 · 交易信號</h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-400">
              掃描全市場、七大技術策略加新聞情緒投票，過五維評分與盈虧比硬門檻才出手。每筆信號附進場區、三段止盈與自適應止損。
            </p>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {STRATS.map((s) => (
                <span key={s} className="rounded-full border border-tide-500/20 bg-tide-500/[0.06] px-2.5 py-0.5 text-[11px] text-tide-300">{s}</span>
              ))}
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button onClick={() => setPricingOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-tide-400 to-tide-600 px-4 py-2 text-sm font-bold text-ink-950 hover:opacity-90">
                <Crown size={15} /> 加入船長艙
              </button>
              <Link href="/signals" className="inline-flex items-center gap-1 rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-200 hover:bg-white/5">
                查看即時信號 <ArrowRight size={14} />
              </Link>
              <span className="text-[11px] text-slate-500">驗證期 · 數據透明 · 不保證獲利</span>
            </div>
          </div>
          <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2 lg:w-[420px]">
            {STRENGTHS.map((f) => (
              <div key={f.t} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <f.icon size={16} className="text-tide-300" />
                <div className="mt-1.5 text-sm font-semibold">{f.t}</div>
                <div className="mt-0.5 text-[11px] leading-snug text-slate-500">{f.d}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
      {/* ===== 大盤狀態 ===== */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="flex items-center gap-3 p-4">
          <FearGauge value={Number(stats?.fearGreed ?? 50)} />
          <div>
            <div className="text-xs text-slate-500">恐懼貪婪</div>
            <div className="font-display text-xl font-bold">{Math.round(Number(stats?.fearGreed ?? 50))}</div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-slate-500">BTC 主導率</div>
          <div className="mt-1 font-display text-xl font-bold">{(Number(stats?.btcDominance ?? 0)).toFixed(1)}%</div>
          <div className="mt-1 text-[11px] text-slate-600">市場資金集中度</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-slate-500">信號勝率（驗證中）</div>
          <div className="mt-1 font-display text-xl font-bold">{stats?.signalWinRate != null ? stats.signalWinRate + "%" : "—"}</div>
          <div className="mt-1 text-[11px] text-slate-600">樣本 {stats?.signalCount ?? 0} 筆</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-slate-500">平均每筆期望值</div>
          <div className={`mt-1 font-display text-xl font-bold ${Number(stats?.ev ?? 0) >= 0 ? "text-up" : "text-down"}`}>
            {stats?.ev != null ? (Number(stats?.ev) >= 0 ? "+" : "") + Number(stats?.ev).toFixed(2) + "%" : "—"}
          </div>
          <div className="mt-1 text-[11px] text-slate-600">毛值（未扣成本）</div>
        </Card>
      </section>
      {/* ===== 主流幣 ===== */}
      <section>
        <SectionTitle title="主流幣 · 即時" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {crypto.length === 0
            ? Array.from({ length: 8 }).map((_, i) => <Card key={i} className="h-24 animate-pulse" />)
            : crypto.slice(0, 12).map((t) => <PriceCard key={t.symbol} t={t} />)}
        </div>
      </section>
      {/* ===== 美股 ===== */}
      {stocks.length > 0 && (
        <section>
          <SectionTitle title="美股 · 即時" />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {stocks.slice(0, 8).map((t) => <PriceCard key={t.symbol} t={t} />)}
          </div>
        </section>
      )}
      {/* ===== 即時 K 線 + 觀察清單 ===== */}
      <section className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Card className="p-3 lg:col-span-2">
          <div className="mb-2 flex items-center gap-2 px-1">
            <span className="font-display text-sm font-bold">{selectedSymbol}/USDT</span>
            <Badge tone="tide">即時 K 線</Badge>
          </div>
          <CandleChart bybitSymbol={selectedSymbol + "USDT"} />
        </Card>
        <Card className="p-3">
          <SectionTitle title="我的觀察" />
          <div className="space-y-1">
            {watched.length === 0 && <div className="px-1 py-2 text-xs text-slate-600">尚未加入觀察，點任一卡片右上角 ★。</div>}
            {watched.map((t) => {
              const up = t.changePct >= 0;
              return (
                <button key={t.symbol} onClick={() => setSymbol(t.symbol)}
                  className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-white/5">
                  <span className="font-mono text-sm font-semibold">{t.symbol}</span>
                  <span className="ml-auto font-mono text-sm">${fmtPrice(t.price)}</span>
                  <span className={`w-16 text-right text-xs ${up ? "text-up" : "text-down"}`}>{fmtPct(t.changePct)}</span>
                </button>
              );
            })}
          </div>
          <div className="mt-2 px-1 text-[10px] text-slate-600">點代號切換上方圖表 · 點主流幣卡看完整詳情</div>
        </Card>
      </section>
    </div>
  );
}
