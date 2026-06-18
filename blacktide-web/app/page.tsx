"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, Radio, ArrowRight, Crown } from "lucide-react";
import { useSession } from "next-auth/react";
import { useMarket } from "@/lib/useMarket";
import { useApp } from "@/lib/store";
import { Card } from "@/components/ui";
import TickerTape from "@/components/TickerTape";
import PriceCard from "@/components/PriceCard";

interface BtcBias { bias: "long" | "short" | "neutral"; action: string; confidence: number; rsi?: number; }

function marketDir(upPct: number, fg: number, btcBias?: string) {
  let score = 0;
  if (upPct >= 0.55) score++; else if (upPct <= 0.45) score--;
  if (fg >= 55) score++;     else if (fg <= 45) score--;
  if (btcBias === "long") score++; else if (btcBias === "short") score--;
  if (score >= 2) return { label: "偏多", tag: "BULLISH", cls: "text-up" };
  if (score <= -2) return { label: "偏空", tag: "BEARISH", cls: "text-down" };
  if (score === 1) return { label: "略偏多", tag: "MILD BULL", cls: "text-up" };
  if (score === -1) return { label: "略偏空", tag: "MILD BEAR", cls: "text-down" };
  return { label: "中性震盪", tag: "NEUTRAL", cls: "text-slate-300" };
}

export default function Home() {
  const { tickers, stats } = useMarket();
  const { setPricingOpen } = useApp();
  const { data: session } = useSession();
  const [btc, setBtc] = useState<BtcBias | null>(null);

  const tier = (session?.user?.tier as string) || "free";
  const crypto = tickers.filter((t) => t.class === "crypto");
  const up = tickers.filter((t) => t.changePct >= 0).length;
  const down = tickers.length - up;
  const fg = Number(stats?.fearGreed ?? 50);
  const dir = marketDir(tickers.length ? up / tickers.length : 0.5, fg, btc?.bias);
  const avgVol = tickers.length ? tickers.reduce((a, t) => a + Math.abs(t.changePct), 0) / tickers.length : 0;

  useEffect(() => {
    fetch("/api/coin?symbol=BTCUSDT")
      .then((r) => r.json())
      .then((d) => setBtc({ bias: d.bias ?? "neutral", action: d.action ?? "", confidence: d.confidence ?? 60, rsi: d.rsi }))
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <TickerTape tickers={tickers} />

      {/* ===== 三秒看懂市場 ===== */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {/* 今日方向 */}
        <Card className="p-5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500">今日方向</div>
          <div className={`font-display text-4xl font-bold ${dir.cls}`}>{dir.label}</div>
          <div className="mt-0.5 text-[10px] tracking-[0.2em] text-slate-600">{dir.tag}</div>
          <div className="mt-4 flex gap-4 text-sm">
            <span><span className="font-bold text-up">{up}</span> <span className="text-xs text-slate-500">上漲</span></span>
            <span><span className="font-bold text-down">{down}</span> <span className="text-xs text-slate-500">下跌</span></span>
          </div>
          <div className="mt-2 flex gap-4 text-xs text-slate-500">
            <span>恐貪 <span className="text-slate-300">{Math.round(fg)}</span></span>
            <span>波動 <span className="text-slate-300">{avgVol.toFixed(1)}%</span></span>
          </div>
        </Card>

        {/* 最新信號 */}
        <Link href="/signals" className="group">
          <Card className="flex h-full flex-col justify-between p-5 transition-all hover:border-tide-500/30 hover:bg-tide-500/[0.04]">
            <div>
              <div className="mb-2 flex items-center gap-2">
                <span className="pulse-dot h-2 w-2 rounded-full bg-tide-400" />
                <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">最新信號</span>
              </div>
              <div className="font-display text-2xl font-bold text-tide-300">黑潮船長</div>
              <div className="mt-2 text-[12px] leading-relaxed text-slate-400">
                掃描 52 幣種 · 7+1 策略投票<br />
                五維評分 + 盈虧比硬門檻過濾
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-tide-300">
              查看即時信號 <ArrowRight size={12} className="transition-transform group-hover:translate-x-0.5" />
            </div>
          </Card>
        </Link>

        {/* AI 觀點 */}
        <Link href="/analysis" className="group">
          <Card className="flex h-full flex-col justify-between p-5 transition-all hover:border-blue-500/30 hover:bg-blue-500/[0.04]">
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Brain size={13} className="text-blue-400" />
                <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">AI 觀點 · BTC</span>
              </div>
              {btc ? (
                <>
                  <div className={`font-display text-xl font-bold ${btc.bias === "long" ? "text-up" : btc.bias === "short" ? "text-down" : "text-amber-400"}`}>
                    {btc.bias === "long" ? "偏多看漲" : btc.bias === "short" ? "偏空看跌" : "震盪待方向"}
                  </div>
                  <div className="mt-1.5 line-clamp-3 text-[12px] leading-relaxed text-slate-400">{btc.action}</div>
                  <div className="mt-2 flex gap-3 text-[11px] text-slate-500">
                    <span>RSI <span className="text-slate-300">{btc.rsi ?? "—"}</span></span>
                    <span>信心 <span className="text-slate-300">{btc.confidence}%</span></span>
                  </div>
                </>
              ) : (
                <div className="mt-1 space-y-2">
                  <div className="h-6 w-32 animate-pulse rounded bg-white/5" />
                  <div className="h-4 w-full animate-pulse rounded bg-white/5" />
                  <div className="h-4 w-3/4 animate-pulse rounded bg-white/5" />
                </div>
              )}
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-blue-400">
              深度 AI 分析 <ArrowRight size={12} className="transition-transform group-hover:translate-x-0.5" />
            </div>
          </Card>
        </Link>
      </div>

      {/* ===== 黑潮 CTA ===== */}
      <section className="relative overflow-hidden rounded-2xl border border-tide-500/25 p-5 sm:p-6"
        style={{ background: "linear-gradient(135deg, rgba(212,175,55,0.10), rgba(10,12,18,0.4))" }}>
        <div className="pointer-events-none absolute -right-10 -top-10 h-48 w-48 rounded-full bg-tide-500/10 blur-3xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold text-gold glow-gold">黑潮 BLACKTIDE · 交易信號</h1>
            <p className="mt-1.5 max-w-md text-sm leading-relaxed text-slate-400">
              七大技術策略加新聞情緒投票，過五維評分與盈虧比硬門檻才出手。三段止盈 40/35/25，波動自適應止損。
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-shrink-0 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
            <button onClick={() => setPricingOpen(true)}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-tide-400 to-tide-600 px-5 py-3 text-sm font-bold text-ink-950 hover:opacity-90 sm:w-auto sm:py-2.5">
              <Crown size={15} /> 加入船長艙
            </button>
            <Link href="/signals"
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-white/10 px-4 py-3 text-sm text-slate-200 hover:bg-white/5 sm:w-auto sm:py-2.5">
              <Radio size={14} /> 查看信號
            </Link>
          </div>
        </div>
      </section>

      {/* ===== 主流幣 ===== */}
      <section>
        <div className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">主流幣 · 即時</div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {crypto.length === 0
            ? Array.from({ length: 8 }).map((_, i) => <Card key={i} className="h-24 animate-pulse" />)
            : crypto.slice(0, 8).map((t) => <PriceCard key={t.symbol} t={t} />)}
        </div>
      </section>

      {/* 手機浮動 CTA（免費用戶） */}
      {tier === "free" && (
        <div className="fixed inset-x-4 bottom-[4.5rem] z-10 md:hidden">
          <button onClick={() => setPricingOpen(true)}
            className="w-full rounded-2xl bg-gradient-to-r from-tide-400 to-tide-600 py-3.5 text-sm font-bold text-ink-950 shadow-xl shadow-tide-500/30">
            <Crown size={14} className="mr-1.5 inline-block" /> 升級解鎖 · 完整交易信號
          </button>
        </div>
      )}
    </div>
  );
}
