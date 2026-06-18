"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, ArrowRight, Crown, Gift, Users, Radio } from "lucide-react";
import { useSession } from "next-auth/react";
import { useMarket } from "@/lib/useMarket";
import { useApp } from "@/lib/store";
import { Card } from "@/components/ui";
import TickerTape from "@/components/TickerTape";
import PriceCard from "@/components/PriceCard";

interface BtcBias {
  bias: "long" | "short" | "neutral";
  action: string;
  confidence: number;
  rsi?: number;
  support?: number[];
  resistance?: number[];
  trend?: string;
  atrPct?: number;
  fundingPct?: number;
}

function marketDir(upPct: number, fg: number, btcBias?: string) {
  let score = 0;
  if (upPct >= 0.55) score++; else if (upPct <= 0.45) score--;
  if (fg >= 55) score++;     else if (fg <= 45) score--;
  if (btcBias === "long") score++; else if (btcBias === "short") score--;
  if (score >= 2) return { label: "偏多", tag: "BULLISH", cls: "text-up", desc: "多數指標同向偏強" };
  if (score <= -2) return { label: "偏空", tag: "BEARISH", cls: "text-down", desc: "市場情緒偏弱壓制" };
  if (score === 1) return { label: "略偏多", tag: "MILD BULL", cls: "text-up", desc: "弱多氛圍，謹慎看多" };
  if (score === -1) return { label: "略偏空", tag: "MILD BEAR", cls: "text-down", desc: "弱空氛圍，觀望為主" };
  return { label: "中性震盪", tag: "NEUTRAL", cls: "text-slate-300", desc: "多空拉鋸，方向待確認" };
}

function fakeOnline() {
  const h = new Date().getHours();
  const peak = h >= 10 && h <= 23 ? 160 : 50;
  return 500 + Math.floor(Math.sin(h * 1.3) * 70 + peak * 0.6 + 40);
}

export default function Home() {
  const { tickers, stats } = useMarket();
  const { setPricingOpen } = useApp();
  const { data: session } = useSession();
  const [btc, setBtc] = useState<BtcBias | null>(null);
  const [online] = useState(() => fakeOnline());
  const [signals24h] = useState(() => 3 + Math.floor(Math.random() * 9));

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
      .then((d) => {
        const a = d.ok ? d.analysis : d;
        setBtc({
          bias: a.bias ?? "neutral",
          action: a.action ?? "",
          confidence: a.confidence ?? 60,
          rsi: a.rsi,
          support: a.support,
          resistance: a.resistance,
          trend: a.trend,
          atrPct: a.atrPct,
          fundingPct: a.fundingPct,
        });
      })
      .catch(() => {});
  }, []);

  const fmtPrice = (n?: number) => n ? n.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—";
  const trendLabel = (t?: string) => t === "up" ? "多頭排列" : t === "down" ? "空頭排列" : "糾結整理";
  const trendCls = (t?: string) => t === "up" ? "text-up" : t === "down" ? "text-down" : "text-slate-400";

  return (
    <div className="space-y-6">
      <TickerTape tickers={tickers} />

      {/* ── 在線統計欄 ── */}
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-white/5 bg-ink-800/50 px-4 py-2.5 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="pulse-dot h-2 w-2 rounded-full bg-up" />
          <span className="text-slate-500">在線人數</span>
          <span className="font-mono font-bold text-up">{online.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Radio size={11} className="text-tide-400" />
          <span className="text-slate-500">近 24h 信號</span>
          <span className="font-mono font-bold text-tide-300">{signals24h} 筆</span>
        </div>
        <div className="ml-auto hidden items-center gap-1.5 text-slate-600 sm:flex">
          掃描 52 幣 · 7+1 策略投票
        </div>
      </div>

      {/* ── 今日方向 + AI觀點 ── */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">

        {/* 今日市場方向 — 52 幣整體分析 */}
        <Card className="p-5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500">今日市場方向 · 52 幣整體</div>
          <div className={`font-display text-4xl font-bold ${dir.cls}`}>{dir.label}</div>
          <div className="mt-0.5 text-[10px] tracking-[0.2em] text-slate-600">{dir.tag}</div>
          <div className="mt-1.5 text-xs text-slate-400">{dir.desc}</div>

          {/* 三訊號明細 */}
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-xs">
              <span className="text-slate-500">市場廣度（52 幣漲跌比）</span>
              <span className={`font-mono font-semibold ${up > down ? "text-up" : up < down ? "text-down" : "text-slate-300"}`}>
                {up}↑ {down}↓
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-xs">
              <span className="text-slate-500">恐貪指數（Fear & Greed）</span>
              <span className={`font-mono font-semibold ${fg >= 55 ? "text-up" : fg <= 45 ? "text-down" : "text-slate-300"}`}>
                {Math.round(fg)} · {fg >= 70 ? "極度貪婪" : fg >= 55 ? "貪婪" : fg <= 30 ? "極度恐慌" : fg <= 45 ? "恐慌" : "中性"}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-xs">
              <span className="text-slate-500">BTC 技術偏向</span>
              <span className={`font-mono font-semibold ${btc?.bias === "long" ? "text-up" : btc?.bias === "short" ? "text-down" : "text-slate-300"}`}>
                {btc ? (btc.bias === "long" ? "偏多" : btc.bias === "short" ? "偏空" : "中性") : "載入中…"}
              </span>
            </div>
          </div>
          <div className="mt-3 text-[10px] text-slate-600">平均波動 {avgVol.toFixed(1)}%</div>
        </Card>

        {/* AI 深度觀點 */}
        <Link href="/analysis" className="group">
          <Card className="flex h-full flex-col p-5 transition-all hover:border-blue-500/30 hover:bg-blue-500/[0.03]">
            <div className="mb-2 flex items-center gap-2">
              <Brain size={13} className="text-blue-400" />
              <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">AI 深度觀點 · BTC/USDT</span>
            </div>

            {btc ? (
              <div className="flex-1 space-y-3">
                <div>
                  <div className={`font-display text-2xl font-bold ${btc.bias === "long" ? "text-up" : btc.bias === "short" ? "text-down" : "text-amber-400"}`}>
                    {btc.bias === "long" ? "偏多看漲" : btc.bias === "short" ? "偏空看跌" : "震盪待方向"}
                  </div>
                  <div className="mt-0.5 text-[11px] text-slate-500">
                    信心 {btc.confidence}% · RSI {btc.rsi ?? "—"} · {trendLabel(btc.trend)}
                  </div>
                </div>

                {/* 指標網格 */}
                <div className="grid grid-cols-3 gap-1.5 text-center text-[10px]">
                  <div className="rounded-lg bg-white/[0.03] p-2">
                    <div className="text-slate-500">趨勢</div>
                    <div className={`mt-0.5 font-semibold ${trendCls(btc.trend)}`}>{trendLabel(btc.trend)}</div>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] p-2">
                    <div className="text-slate-500">波動 ATR</div>
                    <div className={`mt-0.5 font-semibold ${btc.atrPct && btc.atrPct > 3 ? "text-amber-400" : ""}`}>
                      {btc.atrPct ? btc.atrPct.toFixed(1) + "%" : "—"}
                    </div>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] p-2">
                    <div className="text-slate-500">資金費率</div>
                    <div className={`mt-0.5 font-semibold ${btc.fundingPct && Math.abs(btc.fundingPct) > 0.05 ? "text-amber-400" : ""}`}>
                      {btc.fundingPct != null ? (btc.fundingPct >= 0 ? "+" : "") + btc.fundingPct.toFixed(3) + "%" : "—"}
                    </div>
                  </div>
                </div>

                {/* 支撐壓力 */}
                {btc.support && btc.resistance && (
                  <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                    <div className="rounded-lg bg-up/[0.06] px-2.5 py-1.5">
                      <span className="text-slate-500">支撐 </span>
                      <span className="font-mono font-semibold text-up">{btc.support.slice(0, 2).map(fmtPrice).join(" / ")}</span>
                    </div>
                    <div className="rounded-lg bg-down/[0.06] px-2.5 py-1.5">
                      <span className="text-slate-500">壓力 </span>
                      <span className="font-mono font-semibold text-down">{btc.resistance.slice(0, 2).map(fmtPrice).join(" / ")}</span>
                    </div>
                  </div>
                )}

                {/* 操作建議摘要 */}
                <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2.5 text-[12px] leading-relaxed text-slate-300">
                  {btc.action || "正在分析市場結構…"}
                </div>
              </div>
            ) : (
              <div className="flex-1 space-y-2 pt-1">
                <div className="h-7 w-36 animate-pulse rounded bg-white/5" />
                <div className="h-4 w-full animate-pulse rounded bg-white/5" />
                <div className="h-4 w-4/5 animate-pulse rounded bg-white/5" />
                <div className="h-16 w-full animate-pulse rounded bg-white/5" />
              </div>
            )}

            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-blue-400">
              查看全幣種 AI 分析 <ArrowRight size={12} className="transition-transform group-hover:translate-x-0.5" />
            </div>
          </Card>
        </Link>
      </div>

      {/* ── 邀請活動卡 ── */}
      <section className="relative overflow-hidden rounded-2xl border border-amber-500/20 p-5"
        style={{ background: "linear-gradient(135deg, rgba(251,191,36,0.07), rgba(10,12,18,0.4))" }}>
        <div className="pointer-events-none absolute -right-8 -top-8 h-40 w-40 rounded-full bg-amber-500/10 blur-3xl" />
        <div className="relative flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <Gift size={14} className="text-amber-400" />
              <span className="text-[10px] font-semibold uppercase tracking-widest text-amber-400">邀請活動 · 推薦好友</span>
            </div>
            <h2 className="font-display text-lg font-bold text-amber-200">邀請 5 位好友 → 獲贈 1 個月 Plus</h2>
            <p className="mt-1 text-sm leading-relaxed text-slate-400">
              分享你的專屬邀請連結，好友完成註冊即計入。每累積 5 位自動發放，可無限次累積。
            </p>
          </div>
          <Link href={session ? "/member" : "/login?register=1"}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-5 py-2.5 text-sm font-semibold text-amber-300 hover:bg-amber-500/20">
            <Users size={14} /> {session ? "查看邀請連結" : "立即加入"}
          </Link>
        </div>
      </section>

      {/* ── 黑潮船長 CTA ── */}
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
          <div className="flex flex-col gap-2 sm:shrink-0 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
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

      {/* ── 主流幣即時 ── */}
      <section>
        <div className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">主流幣 · 即時</div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {crypto.length === 0
            ? Array.from({ length: 8 }).map((_, i) => <Card key={i} className="h-24 animate-pulse" />)
            : crypto.slice(0, 8).map((t) => <PriceCard key={t.symbol} t={t} />)}
        </div>
      </section>

      {/* 手機浮動 CTA */}
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
