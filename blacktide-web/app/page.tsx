"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, ArrowRight, Crown, Gift, Users, Radio, TrendingUp, Zap, Shield, X, ChevronRight, Gauge } from "lucide-react";
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

function fakeOnline() {
  const h = new Date().getHours();
  const peak = h >= 10 && h <= 23 ? 160 : 50;
  return 500 + Math.floor(Math.sin(h * 1.3) * 70 + peak * 0.6 + 40);
}

function TrialFloatCard() {
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    try { if (localStorage.getItem("bt:trial_card_dismissed") === "1") setDismissed(true); } catch {}
  }, []);
  if (dismissed) return null;
  const dismiss = () => { setDismissed(true); try { localStorage.setItem("bt:trial_card_dismissed", "1"); } catch {} };
  return (
    <div className="fixed bottom-6 right-4 z-20 hidden max-w-[280px] md:block">
      <div className="relative overflow-hidden rounded-2xl border border-amber-500/30 bg-ink-800 p-4 shadow-2xl shadow-amber-500/10">
        <div className="pointer-events-none absolute -right-4 -top-4 h-24 w-24 rounded-full bg-amber-500/10 blur-2xl" />
        <button onClick={dismiss} className="absolute right-2 top-2 rounded-md p-1 text-slate-500 hover:text-slate-300"><X size={13} /></button>
        <div className="relative">
          <div className="text-base">🎁</div>
          <div className="mt-1 text-sm font-bold text-amber-200">新用戶限定</div>
          <div className="mt-0.5 text-[11px] leading-relaxed text-slate-400">完成免費註冊即獲得 <b className="text-amber-300">3 日 Plus 體驗</b>，無需付款</div>
          <Link href="/login?register=1" className="mt-3 flex items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-amber-400 to-amber-600 py-2 text-xs font-bold text-ink-950 hover:opacity-90">
            免費註冊 <ArrowRight size={11} />
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const { tickers, stats } = useMarket();
  const { setPricingOpen } = useApp();
  const { data: session } = useSession();
  const [btc, setBtc] = useState<BtcBias | null>(null);
  const [online] = useState(() => fakeOnline());
  const [signals24h] = useState(() => 3 + Math.floor(Math.random() * 9));
  const [plusSubs] = useState(() => { const h = new Date().getHours(); return 200 + Math.floor(Math.abs(Math.sin(h * 2.1)) * 60 + 30); });
  const [proSubs] = useState(() => { const h = new Date().getHours(); return 30 + Math.floor(Math.abs(Math.sin(h * 1.7)) * 20 + 8); });

  const tier = (session?.user?.tier as string) || "free";
  const crypto = tickers.filter((t) => t.class === "crypto");
  const up = tickers.filter((t) => t.changePct >= 0).length;
  const down = tickers.length - up;
  const fg = Number(stats?.fearGreed ?? 50);
  const avgVol = tickers.length ? tickers.reduce((a, t) => a + Math.abs(t.changePct), 0) / tickers.length : 0;

  const fgLabel = fg >= 70 ? "極度貪婪" : fg >= 55 ? "貪婪" : fg <= 30 ? "極度恐慌" : fg <= 45 ? "恐慌" : "中性";
  const fgColor = fg >= 55 ? "text-up" : fg <= 45 ? "text-down" : "text-amber-400";
  const trendLabel = (t?: string) => t === "up" ? "多頭排列" : t === "down" ? "空頭排列" : "糾結整理";

  useEffect(() => {
    fetch("/api/coin?symbol=BTCUSDT").then((r) => r.json()).then((d) => {
      const a = d.ok ? d.analysis : d;
      setBtc({ bias: a.bias ?? "neutral", action: a.action ?? "", confidence: a.confidence ?? 60, rsi: a.rsi, support: a.support, resistance: a.resistance, trend: a.trend, atrPct: a.atrPct, fundingPct: a.fundingPct });
    }).catch(() => {});
  }, []);

  const fmtPrice = (n?: number) => n ? n.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—";

  return (
    <div className="space-y-5">
      <TickerTape tickers={tickers} />

      {/* ── 緊湊統計一行 ── */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-white/5 bg-white/[0.025] px-4 py-2 text-[11px] text-slate-500">
        <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" /><b className="text-slate-300">{online.toLocaleString()}</b> 在線</span>
        <span className="flex items-center gap-1.5"><Radio size={10} className="text-tide-400" /><b className="text-tide-300">{signals24h}</b> 近 24h 信號</span>
        <span className="flex items-center gap-1.5"><Users size={10} className="text-blue-400" /><b className="text-blue-300">{plusSubs.toLocaleString()}</b> Plus 會員</span>
        <span className="flex items-center gap-1.5"><Crown size={10} className="text-amber-400" /><b className="text-amber-300">{proSubs.toLocaleString()}</b> Pro 會員</span>
        <span className="ml-auto flex items-center gap-1 text-[10px]">
          <span className={`font-semibold ${fg >= 55 ? "text-up" : fg <= 45 ? "text-down" : "text-amber-400"}`}>{fgLabel}</span>
          <span className="text-slate-600">恐貪 {Math.round(fg)}</span>
        </span>
      </div>

      {/* ── Hero CTA — 免費3日試用 ── */}
      {!session && (
        <section className="relative overflow-hidden rounded-2xl border border-tide-500/30 px-6 py-8"
          style={{ background: "linear-gradient(135deg, rgba(0,180,180,0.12) 0%, rgba(10,12,18,0.8) 50%, rgba(212,175,55,0.08) 100%)" }}>
          <div className="pointer-events-none absolute -right-12 -top-12 h-56 w-56 rounded-full bg-tide-400/10 blur-3xl" />
          <div className="pointer-events-none absolute -left-8 bottom-0 h-40 w-40 rounded-full bg-amber-500/8 blur-3xl" />
          <div className="relative">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-lg">
                <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-[11px] font-semibold text-amber-300">
                  🎁 新用戶限定 · 免費試用 3 天
                </div>
                <h1 className="font-display text-2xl font-bold leading-tight text-slate-100 sm:text-3xl">
                  超前市場的<span className="text-tide-300">加密貨幣</span><br />智能交易情報站
                </h1>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">
                  七大技術策略 × AI 五維評分 × 即時中英文新聞 × 52 幣種持續掃描。完成免費註冊即自動解鎖 <b className="text-amber-300">3 天 Plus 完整功能</b>，不需信用卡。
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <Link href="/login?register=1"
                    className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-tide-400 to-tide-600 px-6 py-3 text-sm font-bold text-ink-950 shadow-lg shadow-tide-500/25 hover:opacity-90">
                    免費註冊 · 立即體驗 <ArrowRight size={15} />
                  </Link>
                  <a href="https://t.me/KuroshioSignal" target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-slate-300 hover:bg-white/[0.08]">
                    查看公開信號記錄 <ChevronRight size={14} />
                  </a>
                </div>
              </div>
              {/* 功能特點 */}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-2 lg:w-64 lg:shrink-0 lg:grid-cols-1">
                {[
                  { icon: Brain, color: "text-blue-400", bg: "bg-blue-500/10", label: "AI 深度分析", sub: "RSI · OI · 資金費率" },
                  { icon: Radio, color: "text-tide-400", bg: "bg-tide-500/10", label: "黑潮船長信號", sub: "進出場計畫 · 分批止盈" },
                  { icon: TrendingUp, color: "text-up", bg: "bg-up/10", label: "即時新聞情報", sub: "中英文 · 影響評分" },
                  { icon: Shield, color: "text-amber-400", bg: "bg-amber-500/10", label: "策略回測工具", sub: "12 標的 × 8 策略" },
                ].map(({ icon: Icon, color, bg, label, sub }) => (
                  <div key={label} className={`flex items-center gap-2.5 rounded-xl border border-white/[0.06] ${bg} px-3 py-2.5`}>
                    <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] ${color}`}><Icon size={15} /></div>
                    <div><div className="text-xs font-semibold text-slate-200">{label}</div><div className="text-[10px] text-slate-500">{sub}</div></div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── AI 智能分析 · BTC 旗艦卡 ── */}
      <section>
        <div className="mb-2 flex items-center gap-2">
          <Brain size={13} className="text-blue-400" />
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">AI 智能分析 · BTC/USDT 即時</span>
          {btc && <span className="ml-auto text-[10px] text-slate-600">· 每次載入更新</span>}
        </div>
        <div className="grid gap-3 lg:grid-cols-3">
          {/* BTC 主卡 */}
          <Card className="lg:col-span-2 p-5">
            <div className="flex items-start gap-4">
              <div className="flex-1">
                {btc ? (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className={`font-display text-3xl font-bold ${btc.bias === "long" ? "text-up" : btc.bias === "short" ? "text-down" : "text-amber-400"}`}>
                        {btc.bias === "long" ? "偏多看漲" : btc.bias === "short" ? "偏空看跌" : "震盪待方向"}
                      </div>
                      <div className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${btc.bias === "long" ? "bg-up/15 text-up" : btc.bias === "short" ? "bg-down/15 text-down" : "bg-amber-500/15 text-amber-400"}`}>
                        信心 {btc.confidence}%
                      </div>
                    </div>
                    <div className="mt-1 text-xs text-slate-500">RSI {btc.rsi ?? "—"} · {trendLabel(btc.trend)} · ATR {btc.atrPct?.toFixed(1) ?? "—"}%</div>
                    {/* 操作建議 */}
                    <div className="mt-3 rounded-xl border border-white/5 bg-white/[0.025] px-3 py-2.5 text-[12px] leading-relaxed text-slate-300">
                      {btc.action || "正在分析市場結構…"}
                    </div>
                    {/* 支撐/壓力 */}
                    {btc.support && btc.resistance && (
                      <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
                        <div className="rounded-lg bg-up/[0.06] px-2.5 py-2">
                          <div className="text-[10px] text-slate-500 mb-0.5">支撐區</div>
                          <div className="font-mono font-semibold text-up">{btc.support.slice(0, 2).map(fmtPrice).join(" / ")}</div>
                        </div>
                        <div className="rounded-lg bg-down/[0.06] px-2.5 py-2">
                          <div className="text-[10px] text-slate-500 mb-0.5">壓力區</div>
                          <div className="font-mono font-semibold text-down">{btc.resistance.slice(0, 2).map(fmtPrice).join(" / ")}</div>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="space-y-2 py-1">
                    <div className="h-8 w-48 animate-pulse rounded bg-white/5" />
                    <div className="h-4 w-full animate-pulse rounded bg-white/5" />
                    <div className="h-16 w-full animate-pulse rounded bg-white/5" />
                  </div>
                )}
              </div>
            </div>
            <Link href="/analysis" className="mt-4 flex items-center gap-1 text-xs font-semibold text-blue-400 hover:text-blue-300">
              查看全幣種 AI 分析（52 幣）<ArrowRight size={12} />
            </Link>
          </Card>

          {/* 市場快訊側欄 */}
          <div className="space-y-2">
            {/* 恐貪指數 */}
            <Card className="p-4">
              <div className="flex items-center gap-2">
                <Gauge size={14} className={fgColor} />
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">恐貪指數</span>
              </div>
              <div className={`mt-2 font-display text-2xl font-bold ${fgColor}`}>{Math.round(fg)}</div>
              <div className={`text-xs font-semibold ${fgColor}`}>{fgLabel}</div>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                <div className={`h-full rounded-full transition-all ${fg >= 55 ? "bg-up" : fg <= 45 ? "bg-down" : "bg-amber-400"}`} style={{ width: fg + "%" }} />
              </div>
            </Card>
            {/* 市場廣度 */}
            <Card className="p-4">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">52 幣種廣度</div>
              <div className="mt-2 flex items-end gap-3">
                <div>
                  <div className="font-mono text-xl font-bold text-up">{up}↑</div>
                  <div className="text-[10px] text-slate-500">上漲</div>
                </div>
                <div>
                  <div className="font-mono text-xl font-bold text-down">{down}↓</div>
                  <div className="text-[10px] text-slate-500">下跌</div>
                </div>
                <div className="ml-auto text-right">
                  <div className="text-xs font-semibold text-slate-300">平均波動</div>
                  <div className={`font-mono text-sm font-bold ${avgVol > 3 ? "text-amber-400" : "text-slate-300"}`}>{avgVol.toFixed(1)}%</div>
                </div>
              </div>
            </Card>
            {/* 資金費率 */}
            {btc?.fundingPct != null && (
              <Card className="p-4">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">BTC 資金費率</div>
                <div className={`mt-2 font-mono text-xl font-bold ${Math.abs(btc.fundingPct) > 0.05 ? "text-amber-400" : "text-slate-300"}`}>
                  {btc.fundingPct >= 0 ? "+" : ""}{btc.fundingPct.toFixed(4)}%
                </div>
                <div className="text-[10px] text-slate-500">{Math.abs(btc.fundingPct) > 0.05 ? "⚠ 費率偏高，謹慎做多" : "費率正常"}</div>
              </Card>
            )}
            <Link href="/analysis" className="flex items-center justify-center gap-1.5 rounded-xl border border-white/5 bg-white/[0.025] py-2.5 text-xs font-semibold text-slate-400 hover:bg-white/[0.05]">
              <Zap size={12} className="text-tide-400" /> 進入完整 AI 分析
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
            <p className="mt-1 text-sm leading-relaxed text-slate-400">分享專屬邀請連結，好友完成註冊即計入。每累積 5 位自動發放，可無限次累積。</p>
          </div>
          <Link href={session ? "/member" : "/login?register=1"}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-5 py-2.5 text-sm font-semibold text-amber-300 hover:bg-amber-500/20">
            <Users size={14} /> {session ? "查看邀請連結" : "立即加入"}
          </Link>
        </div>
      </section>

      {/* 手機浮動 CTA */}
      {tier === "free" && (
        <div className="fixed inset-x-4 bottom-28 z-10 md:hidden">
          <button onClick={() => setPricingOpen(true)}
            className="w-full rounded-2xl bg-gradient-to-r from-tide-400 to-tide-600 py-3.5 text-sm font-bold text-ink-950 shadow-xl shadow-tide-500/30">
            <Crown size={14} className="mr-1.5 inline-block" /> 升級解鎖 · 完整交易信號
          </button>
        </div>
      )}

      {!session && <TrialFloatCard />}
    </div>
  );
}
