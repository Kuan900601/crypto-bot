"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, ArrowRight, Crown, Gift, Users, Radio, TrendingUp, Zap, X, Gauge, Lock } from "lucide-react";
import { useSession } from "next-auth/react";
import { useMarket } from "@/lib/useMarket";
import { useApp } from "@/lib/store";
import { Card } from "@/components/ui";
import TickerTape from "@/components/TickerTape";
import PriceCard from "@/components/PriceCard";
import { Signal } from "@/lib/types";

// 監測幣種數固定為 52（analyzer.py 實際掃描的幣種數，與站內既有文案一致）
const MONITORED_COINS = 52;

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

function isToday(iso?: string) {
  if (!iso) return false;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return false;
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
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
            免費註冊 · 查看今日信號 <ArrowRight size={11} />
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
  const [signals, setSignals] = useState<Signal[] | null>(null);

  const tier = (session?.user?.tier as string) || "free";

  useEffect(() => {
    fetch("/api/signals").then((r) => r.json()).then((d) => setSignals(d.signals ?? null)).catch(() => {});
  }, []);

  const todaySignalCount = (signals || []).filter((s) => isToday(s.openedAt)).length;
  const previewSignal = (signals || []).find((s) => s.status === "active") || (signals || [])[0] || null;

  // 真實已結算信號績效（依 /api/signals 回傳的 finalPct 計算，無捏造數字）
  const closedSignals = (signals || []).filter((s) => s.status !== "active" && typeof s.finalPct === "number");
  const chronological = [...closedSignals].reverse(); // API 回傳新到舊，轉成舊到新算回撤
  const perfWins = chronological.filter((s) => (s.finalPct ?? 0) > 0).length;
  const perfWinRate = chronological.length ? Math.round((perfWins / chronological.length) * 100) : 0;
  const perfAvgPct = chronological.length ? chronological.reduce((a, s) => a + (s.finalPct ?? 0), 0) / chronological.length : 0;
  let perfPeak = 0, perfCum = 0, perfMaxDD = 0;
  for (const s of chronological) {
    perfCum += s.finalPct ?? 0;
    if (perfCum > perfPeak) perfPeak = perfCum;
    const dd = perfPeak - perfCum;
    if (dd > perfMaxDD) perfMaxDD = dd;
  }
  const perfSampleOk = chronological.length >= 5;
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
        <span className="flex items-center gap-1.5"><Zap size={10} className="text-tide-400" /><b className="text-slate-300">{MONITORED_COINS}</b> 監測幣種</span>
        <span className="flex items-center gap-1.5"><Radio size={10} className="text-tide-400" /><b className="text-tide-300">{todaySignalCount}</b> 今日信號</span>
        <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" /><b className="text-slate-300">24/7</b> AI 盯盤</span>
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
                  AI 24 小時盯盤<br /><span className="text-tide-300">幫你抓加密貨幣交易信號</span>
                </h1>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">
                  登入即可查看今日 AI 分析、方向判斷與部分交易信號。<br />升級 Pro 解鎖進場、止損與 TP 點位。
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <Link href="/login?register=1"
                    className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-tide-400 to-tide-600 px-6 py-3 text-sm font-bold text-ink-950 shadow-lg shadow-tide-500/25 hover:opacity-90">
                    免費註冊 · 查看今日信號 <ArrowRight size={15} />
                  </Link>
                </div>
                <p className="mt-2 text-[11px] text-slate-500">不需信用卡</p>
              </div>

              {/* ── 今日 AI 信號預覽（真實資料，價位鎖定） ── */}
              {previewSignal && (
                <div className="w-full max-w-xs shrink-0 rounded-2xl border border-tide-500/25 bg-white/[0.03] p-4 backdrop-blur-sm lg:max-w-[260px]">
                  <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">今日 AI 信號預覽</div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-base font-bold text-slate-100">{previewSignal.symbol}/USDT</span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${previewSignal.direction === "long" ? "bg-up/15 text-up" : "bg-down/15 text-down"}`}>
                      {previewSignal.direction === "long" ? "做多" : "做空"}
                    </span>
                  </div>
                  <div className="mt-1.5 text-xs text-slate-400">勝率：<b className="text-tide-300">{Math.round(previewSignal.winRate ?? 0)}%</b></div>
                  <div className="mt-3 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between"><span className="text-slate-500">進場價</span><span className="flex items-center gap-1 text-slate-500"><Lock size={11} />登入解鎖</span></div>
                    <div className="flex items-center justify-between"><span className="text-slate-500">止損價</span><span className="flex items-center gap-1 text-slate-500"><Lock size={11} />登入解鎖</span></div>
                    <div className="flex items-center justify-between"><span className="text-slate-500">TP1</span><span className="flex items-center gap-1 text-slate-500"><Lock size={11} />登入解鎖</span></div>
                  </div>
                  <Link href="/login?register=1"
                    className="mt-3 flex items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-tide-400 to-tide-600 py-2.5 text-xs font-bold text-ink-950 hover:opacity-90">
                    免費註冊 · 查看完整信號 <ArrowRight size={12} />
                  </Link>
                </div>
              )}
            </div>

            {/* ── 真實績效（依已結算信號計算，樣本不足不強調數字） ── */}
            <div className="mt-5 max-w-md rounded-2xl border border-white/5 bg-white/[0.02] p-4">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                {perfSampleOk ? `最近 ${chronological.length} 筆已結算信號` : "信號績效"}
              </div>
              {perfSampleOk ? (
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div>
                    <div className="font-mono text-lg font-bold text-up">{perfWinRate}%</div>
                    <div className="text-[10px] text-slate-500">勝率</div>
                  </div>
                  <div>
                    <div className={`font-mono text-lg font-bold ${perfAvgPct >= 0 ? "text-up" : "text-down"}`}>{perfAvgPct >= 0 ? "+" : ""}{perfAvgPct.toFixed(1)}%</div>
                    <div className="text-[10px] text-slate-500">平均報酬</div>
                  </div>
                  <div>
                    <div className="font-mono text-lg font-bold text-down">-{perfMaxDD.toFixed(1)}%</div>
                    <div className="text-[10px] text-slate-500">最大回撤</div>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-slate-500">樣本仍在累積中，待已結算信號足量後將公開實際績效數字。</div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ── 功能介紹 · 四張實際功能卡 ── */}
      {!session && (
        <section>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              { icon: Radio, label: "黑潮船長信號", sub: "進出場計畫 · 分批止盈 · 即時推播", note: "免費看方向與結果，升級 Plus 解鎖完整進出場價位" },
              { icon: Brain, label: "AI 五維分析", sub: "趨勢 · 動量 · 結構 · 量能 · 風險，逐幣評分" },
              { icon: TrendingUp, label: "即時新聞情報", sub: "中英文來源 · 影響評分 · 異常監控" },
              { icon: Zap, label: "52 幣種掃描", sub: "持續監測主流與熱門幣，不錯過機會" },
            ].map(({ icon: Icon, label, sub, note }) => (
              <div key={label} className="relative overflow-hidden rounded-2xl border border-amber-500/20 bg-white/[0.025] p-4 backdrop-blur-sm">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400"><Icon size={17} /></div>
                <div className="mt-3 text-sm font-bold text-slate-100">{label}</div>
                <div className="mt-1 text-[11px] leading-relaxed text-slate-400">{sub}</div>
                {note && <div className="mt-2 text-[10px] leading-relaxed text-amber-300/80">{note}</div>}
              </div>
            ))}
          </div>
          <div className="mt-4 flex justify-center">
            <Link href="/login?register=1"
              className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-5 py-2.5 text-sm font-semibold text-amber-300 hover:bg-amber-500/20">
              免費註冊 · 查看今日信號 <ArrowRight size={14} />
            </Link>
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
          {!session ? (
            <Link href="/login?register=1"
              className="block w-full rounded-2xl bg-gradient-to-r from-tide-400 to-tide-600 py-3.5 text-center text-sm font-bold text-ink-950 shadow-xl shadow-tide-500/30">
              <Crown size={14} className="mr-1.5 inline-block" /> 登入解鎖完整信號
            </Link>
          ) : (
            <button onClick={() => setPricingOpen(true)}
              className="w-full rounded-2xl bg-gradient-to-r from-tide-400 to-tide-600 py-3.5 text-sm font-bold text-ink-950 shadow-xl shadow-tide-500/30">
              <Crown size={14} className="mr-1.5 inline-block" /> 升級解鎖 · 完整交易信號
            </button>
          )}
        </div>
      )}

      {!session && <TrialFloatCard />}
    </div>
  );
}
