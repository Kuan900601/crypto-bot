"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Lock, TrendingUp, TrendingDown, Radar, Radio, Clock,
  Trophy, BarChart2, AlertTriangle, BrainCircuit, Gauge, Crosshair, Activity,
  ChevronDown, ArrowRight, ScanSearch, Send, ShieldCheck,
} from "lucide-react";
import { useSession } from "next-auth/react";
import { useMarket } from "@/lib/useMarket";
import { Signal } from "@/lib/types";
import TickerTape from "@/components/TickerTape";
import { C, MONO } from "@/lib/theme";
import CTA from "@/components/site/CTA";
import Counter from "@/components/site/Counter";
import SignalShowcase from "@/components/site/SignalShowcase";
import { useTilt } from "@/lib/useTilt";
import { Skeleton } from "@/components/ui";

// 監測幣種數固定為 52（analyzer.py 實際掃描的幣種數，與站內既有文案一致，非首頁自行估算）
const MONITORED_COINS = 52;

// Tier 層級：同一青色主色，用強度做層級（S 最亮最實、C 最淡），符合單一 accent 原則
const TIER_COLOR: Record<string, { color: string; bg: string; border: string }> = {
  S: { color: "#00D4FF", bg: "rgba(0,212,255,0.16)",   border: "rgba(0,212,255,0.5)"    },
  A: { color: "#67E8F9", bg: "rgba(103,232,249,0.1)",  border: "rgba(103,232,249,0.35)" },
  B: { color: "#64748B", bg: "rgba(100,116,139,0.12)", border: "rgba(100,116,139,0.38)" },
  C: { color: "#64748B", bg: "transparent",            border: "rgba(255,255,255,0.08)" },
};
function gradeColor(g: string) {
  if (g === "S" || g === "A") return { color: "#10B981", label: "高品質進場" };
  if (g === "B" || g === "C") return { color: "#94A3B8", label: "一般品質"   };
  return { color: "#64748B", label: "低品質" };
}

function isToday(iso?: string) {
  if (!iso) return false;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return false;
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

const FEATURES = [
  { Icon: BrainCircuit, title: "7+1 策略投票引擎", desc: "趨勢、動能、結構等多策略共識決定方向，單一策略偏誤不足以觸發信號。" },
  { Icon: Gauge, title: "五維評分與分級", desc: "每個信號經綜合評分後標記 S / A / B / C 分級與進場品質，強弱一目了然。" },
  { Icon: Crosshair, title: "進出場紀律", desc: "進場區間、止損、分批止盈一次給齊；觸及止盈後移動止損鎖利，不憑感覺操作。" },
  { Icon: Activity, title: "全市場異常監控", desc: "爆倉潮、資金費率異常、巨量成交即時捕捉，市場異動第一時間掌握。" },
];

const WORKFLOW = [
  { Icon: ScanSearch, step: "01", title: "AI 全天候掃描", desc: `${MONITORED_COINS} 幣種 24/7 監控，多策略投票 + 五維評分過濾雜訊。` },
  { Icon: Send, step: "02", title: "信號分級推送", desc: "通過門檻的信號附完整進場區間、止損與分批 TP，並標記分級。" },
  { Icon: ShieldCheck, step: "03", title: "紀律化管理", desc: "分批止盈、移動止損、結構退出全程追蹤，每筆結果照實結算公開。" },
];

const FAQS = [
  { q: "信號多久更新一次？", a: "AI 全天候掃描 52 個幣種，信號依市場條件即時產生，不是固定排程。有新信號會即時出現在網站與推播渠道。" },
  { q: "免費帳號能看到什麼？", a: "免費帳號可以看到信號方向、分級與已結算的真實損益。完整的進場區間、止損與分批止盈價位需要付費方案解鎖。" },
  { q: "績效數字是真實的嗎？", a: "是。已結算信號的損益百分比照實顯示，有賺有賠不做篩選。歷史績效不代表未來報酬，請自行評估風險。" },
  { q: "訂閱會自動扣款嗎？", a: "不會。付款採加密貨幣（NOWPayments），單次付清，到期不自動續扣；到期前站內會提醒續訂。" },
];

function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div style={{ maxWidth: 640, margin: "0 auto", display: "flex", flexDirection: "column", gap: 10 }}>
      {FAQS.map((f, i) => {
        const on = open === i;
        return (
          <div key={f.q} style={{ borderRadius: 14, border: `1px solid ${on ? C.linePrimary : C.line}`, background: C.deep, overflow: "hidden", transition: "border-color .2s" }}>
            <button onClick={() => setOpen(on ? null : i)} className="press-feedback" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", padding: "16px 18px", background: "transparent", border: "none", cursor: "pointer", color: C.ink, fontSize: 14.5, fontWeight: 600, textAlign: "left" }}>
              {f.q}
              <ChevronDown size={16} color={C.dim} style={{ transform: on ? "rotate(180deg)" : "none", transition: "transform .2s", flexShrink: 0, marginLeft: 12 }} />
            </button>
            {on && (
              <div style={{ padding: "0 18px 16px", fontSize: 13.5, lineHeight: 1.7, color: C.mut }}>{f.a}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function Home() {
  const { tickers, stats } = useMarket();
  const { data: session } = useSession();
  const [signals, setSignals] = useState<Signal[] | null>(null);
  const previewTiltRef = useTilt<HTMLDivElement>(5);

  useEffect(() => {
    fetch("/api/signals").then((r) => r.json()).then((d) => setSignals(d.signals ?? null)).catch(() => {});
  }, []);

  const todaySignalCount = (signals || []).filter((s) => isToday(s.openedAt)).length;
  const previewSignal = (signals || []).find((s) => s.status === "active") || (signals || [])[0] || null;

  // 真實已結算信號績效（依 finalPct 計算；entry/sl/tp 價位不在這裡用，僅算勝率/報酬/回撤）
  const closedSignals = (signals || []).filter((s) => s.status !== "active" && typeof s.finalPct === "number");
  const chronological = [...closedSignals].reverse(); // API 回傳新到舊，轉成舊到新才能算回撤
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

  const fg = stats?.fearGreed;
  const fgTone = fg == null ? C.mut : fg < 45 ? C.rose : fg > 55 ? C.green : C.amber;
  const fgLabel = fg == null ? "—" : fg < 25 ? "極度恐懼" : fg < 45 ? "恐懼" : fg <= 55 ? "中性" : fg <= 75 ? "貪婪" : "極度貪婪";

  return (
    <div>
      {/* ============ Hero：排版主導、低噪點綴（REDESIGN V1） ============ */}
      <section style={{ position: "relative", overflow: "hidden", borderRadius: 20, padding: "clamp(56px,9vh,96px) 22px clamp(44px,7vh,72px)" }}>
        {/* 背景：頂部單一青色微光 + 細格線，取代舊燈塔/海浪特效 */}
        <div aria-hidden style={{ position: "absolute", inset: 0, pointerEvents: "none", background: "radial-gradient(900px 420px at 50% -8%, rgba(0,212,255,0.09), transparent 62%)" }} />
        <div aria-hidden style={{
          position: "absolute", inset: 0, pointerEvents: "none", opacity: 0.5,
          backgroundImage: `linear-gradient(${C.line} 1px, transparent 1px), linear-gradient(90deg, ${C.line} 1px, transparent 1px)`,
          backgroundSize: "56px 56px",
          maskImage: "radial-gradient(720px 380px at 50% 0%, #000 30%, transparent 78%)",
          WebkitMaskImage: "radial-gradient(720px 380px at 50% 0%, #000 30%, transparent 78%)",
        }} />

        <div style={{ position: "relative", zIndex: 2, maxWidth: 1120, margin: "0 auto" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 48, alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ maxWidth: 580, flex: "1 1 360px" }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 8, marginBottom: 24, padding: "6px 14px", borderRadius: 999, fontSize: 12, fontWeight: 600, color: C.primary, border: `1px solid ${C.linePrimary}`, background: "rgba(0,212,255,0.06)" }}>
                <span className="pulse-live" />
                {MONITORED_COINS} 幣種 · 24/7 AI 盯盤
              </div>
              <h1 style={{ fontWeight: 800, lineHeight: 1.18, margin: 0, fontSize: "clamp(38px,5.6vw,62px)", letterSpacing: "-0.02em", color: C.ink, wordBreak: "keep-all", overflowWrap: "break-word" }}>
                專業 AI 交易情報，<br />
                <span style={{ color: C.primary }}>紀律化</span>進出場
              </h1>
              <p style={{ fontSize: "clamp(15px,1.8vw,17px)", lineHeight: 1.7, color: C.mut, margin: "20px 0 0", maxWidth: 460, wordBreak: "keep-all", overflowWrap: "break-word" }}>
                {session
                  ? <>歡迎回來。AI 持續掃描市場，下面是今日分析與照實結算的信號戰績。</>
                  : <>多策略投票產出可執行的交易信號——進場區間、止損、分批止盈一次給齊，每筆結果照實公開。</>}
              </p>
              <div style={{ display: "flex", gap: 12, marginTop: 30, flexWrap: "wrap", alignItems: "center" }}>
                {session ? (
                  <Link href="/signals"><CTA big>前往信號中心</CTA></Link>
                ) : (
                  <Link href="/login?register=1"><CTA big>免費註冊 · 送 3 日 Plus 體驗</CTA></Link>
                )}
                <Link href="/signals" style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "15px 22px", borderRadius: 12, fontSize: 15, fontWeight: 600, color: C.ink, border: `1px solid ${C.line}`, background: "rgba(255,255,255,0.03)" }} className="press-feedback">
                  查看信號戰績 <ArrowRight size={15} />
                </Link>
              </div>

              {/* 真實統計列 */}
              <div style={{ display: "flex", gap: 30, marginTop: 44, flexWrap: "wrap" }}>
                {([
                  { n: MONITORED_COINS, label: "監測幣種", sub: "永續合約", Icon: Radar },
                  { n: todaySignalCount, label: "今日信號", sub: "已發出", Icon: Radio },
                ] as const).map(({ n, label, sub, Icon }) => (
                  <div key={label}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Icon size={14} color={C.primary} style={{ opacity: 0.7 }} />
                      <div style={{ fontFamily: MONO, fontSize: 26, fontWeight: 800, color: C.ink }}><Counter to={n} /></div>
                    </div>
                    <div style={{ fontSize: 11, color: C.dim, marginTop: 2, letterSpacing: 1 }}>{label} <span style={{ opacity: 0.6 }}>· {sub}</span></div>
                  </div>
                ))}
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Clock size={14} color={C.primary} style={{ opacity: 0.7 }} />
                    <div style={{ fontFamily: MONO, fontSize: 26, fontWeight: 800, color: C.ink }}>24/7</div>
                  </div>
                  <div style={{ fontSize: 11, color: C.dim, marginTop: 2, letterSpacing: 1 }}>AI 盯盤 <span style={{ opacity: 0.6 }}>· 不停機</span></div>
                </div>
                {fg != null && (
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Gauge size={14} color={fgTone} style={{ opacity: 0.85 }} />
                      <div style={{ fontFamily: MONO, fontSize: 26, fontWeight: 800, color: fgTone }}>{fg}</div>
                    </div>
                    <div style={{ fontSize: 11, color: C.dim, marginTop: 2, letterSpacing: 1 }}>恐懼貪婪 <span style={{ opacity: 0.6 }}>· {fgLabel}</span></div>
                  </div>
                )}
              </div>
            </div>

            {/* 今日 AI 信號預覽（真實資料；信心為模型評分，非已實現歷史勝率） */}
            {signals === null && (
              <div style={{ flex: "0 1 300px", minWidth: 260, borderRadius: 16, padding: 20, background: C.deep, border: `1px solid ${C.line}` }}>
                <Skeleton className="h-2.5 w-24" />
                <div style={{ marginTop: 12, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <Skeleton className="h-5 w-20" />
                  <Skeleton className="h-4 w-12 rounded-full" />
                </div>
                <Skeleton className="mt-3 h-3 w-32" />
                <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-full" />
                </div>
              </div>
            )}
            {previewSignal && (
              <div ref={previewTiltRef} className="tilt-card" style={{ flex: "0 1 300px", minWidth: 260, borderRadius: 16, padding: 20, background: C.deep, border: `1px solid ${C.line}`, boxShadow: "0 20px 60px rgba(0,0,0,.35)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <span style={{ fontSize: 10.5, letterSpacing: 2, color: C.dim }}>今日 AI 信號預覽</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 10.5, color: C.primary }}><span className="pulse-live" />LIVE</span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  {previewSignal.direction === "long"
                    ? <TrendingUp size={20} color={C.green} />
                    : <TrendingDown size={20} color={C.rose} />}
                  <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 18, color: C.ink }}>{previewSignal.symbol}/USDT</span>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "3px 9px", borderRadius: 99, marginLeft: "auto",
                    color: previewSignal.direction === "long" ? C.green : C.rose,
                    background: (previewSignal.direction === "long" ? C.green : C.rose) + "1A" }}>
                    {previewSignal.direction === "long" ? "做多" : "做空"}
                  </span>
                </div>

                <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
                  {(() => { const tc = TIER_COLOR[previewSignal.tier] ?? TIER_COLOR["C"]; return (
                    <span style={{ fontSize: 9.5, fontWeight: 700, padding: "2px 8px", borderRadius: 6, color: tc.color, background: tc.bg, border: `1px solid ${tc.border}` }}>
                      Tier {previewSignal.tier}
                    </span>
                  ); })()}
                  {(() => { const gc = gradeColor(previewSignal.entryGrade); return (
                    <span style={{ fontSize: 9.5, fontWeight: 600, padding: "2px 8px", borderRadius: 6, color: gc.color, background: gc.color + "18", border: `1px solid ${gc.color}44` }}>
                      {gc.label}
                    </span>
                  ); })()}
                  {previewSignal.leverage != null && (
                    <span style={{ fontSize: 9.5, fontWeight: 600, padding: "2px 8px", borderRadius: 6, color: C.dim, border: `1px solid ${C.line}` }}>
                      {previewSignal.leverage}x
                    </span>
                  )}
                </div>

                <div style={{ marginBottom: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, color: C.mut, marginBottom: 4 }}>
                    <span>AI 信心評分</span>
                    <b style={{ color: C.primary, fontFamily: MONO }}>{Math.round(previewSignal.winRate ?? 0)}%</b>
                  </div>
                  <div style={{ height: 4, borderRadius: 99, background: "rgba(255,255,255,0.06)" }}>
                    <div style={{ height: "100%", borderRadius: 99, width: `${Math.min(100, Math.round(previewSignal.winRate ?? 0))}%`, background: C.primary }} />
                  </div>
                  <div style={{ fontSize: 9, color: C.dim, marginTop: 3 }}>模型評分，非已實現歷史勝率</div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 7, fontSize: 12.5 }}>
                  {previewSignal.entryLow != null ? (
                    <Row label="進場價" value={"$" + previewSignal.entryLow} />
                  ) : (
                    <LockedRow label="進場價" />
                  )}
                  {previewSignal.stopLoss != null ? (
                    <Row label="止損價" value={"$" + previewSignal.stopLoss} color={C.rose} />
                  ) : (
                    <LockedRow label="止損價" />
                  )}
                  {previewSignal.tps?.[0]?.price != null ? (
                    <Row label="TP1" value={"$" + previewSignal.tps[0].price} color={C.green} />
                  ) : (
                    <LockedRow label="TP1" />
                  )}
                </div>
                {!session && (
                  <Link href="/login?register=1" style={{ display: "block", marginTop: 16 }}>
                    <CTA style={{ width: "100%", padding: "11px 0", fontSize: 13 }}>免費註冊 · 查看完整信號</CTA>
                  </Link>
                )}
              </div>
            )}
          </div>

          {/* 近 N 筆已結算信號績效（樣本不足不強調具體數字） */}
          <div style={{ marginTop: 40, maxWidth: 520, borderRadius: 14, padding: 18, background: C.deep, border: `1px solid ${C.line}` }}>
            <div style={{ fontSize: 11, letterSpacing: 2, color: C.dim, marginBottom: 12 }}>
              {signals === null ? "信號績效" : perfSampleOk ? `近 ${chronological.length} 筆已結算信號` : "信號績效"}
            </div>
            {signals === null ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
                {[0, 1, 2].map((i) => (
                  <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                    <Skeleton className="h-4 w-10" />
                    <Skeleton className="h-2.5 w-8" />
                  </div>
                ))}
              </div>
            ) : perfSampleOk ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, textAlign: "center" }}>
                <div>
                  <div style={{ fontFamily: MONO, fontSize: 20, fontWeight: 800, color: C.green }}>{perfWinRate}%</div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, fontSize: 10, color: C.dim, marginTop: 3 }}>
                    <Trophy size={10} />勝率
                  </div>
                </div>
                <div>
                  <div style={{ fontFamily: MONO, fontSize: 20, fontWeight: 800, color: perfAvgPct >= 0 ? C.green : C.rose }}>{perfAvgPct >= 0 ? "+" : ""}{perfAvgPct.toFixed(1)}%</div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, fontSize: 10, color: C.dim, marginTop: 3 }}>
                    <BarChart2 size={10} />平均報酬
                  </div>
                </div>
                <div>
                  <div style={{ fontFamily: MONO, fontSize: 20, fontWeight: 800, color: C.rose }}>-{perfMaxDD.toFixed(1)}%</div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, fontSize: 10, color: C.dim, marginTop: 3 }}>
                    <AlertTriangle size={10} />最大回撤
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ fontSize: 12.5, color: C.mut, lineHeight: 1.6, wordBreak: "keep-all", overflowWrap: "break-word" }}>
                樣本仍在累積中，待已結算信號足量後將公開實際績效數字。目前可確認：{MONITORED_COINS} 幣種監測、7+1 策略投票、分批止盈紀律、24/7 AI 盯盤。
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ============ 行情跑馬燈（真實 /api/market，每 60 秒刷新 + WS 即時價） ============ */}
      <div style={{ marginTop: 24 }}>
        <TickerTape tickers={tickers} />
      </div>

      {/* ============ 核心能力（真實功能描述，非行銷數字） ============ */}
      <section style={{ padding: "72px 22px 8px" }}>
        <div style={{ maxWidth: 1120, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 40 }}>
            <div style={{ fontSize: 12, letterSpacing: 4, color: C.primary, fontWeight: 700, marginBottom: 14 }}>CAPABILITIES</div>
            <h2 style={{ fontSize: "clamp(26px,4vw,40px)", fontWeight: 800, color: C.ink, margin: 0, letterSpacing: "-0.02em", lineHeight: 1.25, wordBreak: "keep-all" }}>
              信號背後的完整系統
            </h2>
            <p style={{ fontSize: 15, color: C.mut, margin: "14px auto 0", maxWidth: 460, lineHeight: 1.65, wordBreak: "keep-all" }}>
              不是單一指標喊單——從掃描、評分、分級到出場管理，每一步都有規則。
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
            {FEATURES.map(({ Icon, title, desc }) => (
              <div key={title} className="press-feedback" style={{ borderRadius: 16, padding: "22px 20px", background: C.deep, border: `1px solid ${C.line}` }}>
                <span style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 40, height: 40, borderRadius: 12, color: C.primary, background: "rgba(0,212,255,0.08)", border: `1px solid ${C.linePrimary}` }}>
                  <Icon size={19} />
                </span>
                <div style={{ marginTop: 14, fontSize: 15.5, fontWeight: 700, color: C.ink }}>{title}</div>
                <div style={{ marginTop: 7, fontSize: 13, lineHeight: 1.65, color: C.mut, wordBreak: "keep-all" }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============ 運作流程 ============ */}
      <section style={{ padding: "64px 22px 8px" }}>
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 36 }}>
            <div style={{ fontSize: 12, letterSpacing: 4, color: C.primary, fontWeight: 700, marginBottom: 14 }}>HOW IT WORKS</div>
            <h2 style={{ fontSize: "clamp(24px,3.6vw,36px)", fontWeight: 800, color: C.ink, margin: 0, letterSpacing: "-0.02em", wordBreak: "keep-all" }}>
              從市場雜訊到可執行信號
            </h2>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
            {WORKFLOW.map(({ Icon, step, title, desc }) => (
              <div key={step} style={{ borderRadius: 16, padding: "22px 20px", background: C.deep, border: `1px solid ${C.line}`, position: "relative" }}>
                <div style={{ fontFamily: MONO, fontSize: 12, fontWeight: 700, color: C.primary, letterSpacing: 2 }}>{step}</div>
                <div style={{ display: "flex", alignItems: "center", gap: 9, marginTop: 10 }}>
                  <Icon size={17} color={C.primary} />
                  <span style={{ fontSize: 15.5, fontWeight: 700, color: C.ink }}>{title}</span>
                </div>
                <div style={{ marginTop: 8, fontSize: 13, lineHeight: 1.65, color: C.mut, wordBreak: "keep-all" }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============ 信號戰績流（真實資料） ============ */}
      <SignalShowcase signals={signals} />

      {/* ============ FAQ ============ */}
      <section style={{ padding: "8px 22px 64px" }}>
        <div style={{ maxWidth: 1120, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 30 }}>
            <div style={{ fontSize: 12, letterSpacing: 4, color: C.primary, fontWeight: 700, marginBottom: 14 }}>FAQ</div>
            <h2 style={{ fontSize: "clamp(22px,3.2vw,32px)", fontWeight: 800, color: C.ink, margin: 0, letterSpacing: "-0.02em" }}>常見問題</h2>
          </div>
          <Faq />
          <div style={{ textAlign: "center", marginTop: 18 }}>
            <Link href="/faq" style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 13, color: C.primary }}>
              查看全部常見問題 <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      </section>

      {/* ============ 結尾轉換區（極簡，聲納特效退場） ============ */}
      <section style={{ padding: "56px 22px 72px", textAlign: "center", position: "relative", overflow: "hidden", borderRadius: 20, background: `radial-gradient(640px 300px at 50% 110%, rgba(0,212,255,0.08), transparent 70%)` }}>
        <div style={{ position: "relative", zIndex: 2, maxWidth: 680, margin: "0 auto" }}>
          <h2 style={{ fontSize: "clamp(26px,4.4vw,42px)", fontWeight: 800, color: C.ink, margin: 0, lineHeight: 1.3, letterSpacing: "-0.02em", wordBreak: "keep-all", overflowWrap: "break-word" }}>
            方向、信號、進場、止損、TP，<br /><span style={{ color: C.primary }}>一站看齊</span>
          </h2>
          <p style={{ fontSize: "clamp(14px,1.9vw,17px)", color: C.mut, margin: "16px 0 0", wordBreak: "keep-all" }}>免費註冊即可開始查看今日信號。</p>
          <div style={{ marginTop: 34 }}>
            {!session && <Link href="/login?register=1"><CTA big>免費註冊 · 送 3 日 Plus 體驗</CTA></Link>}
            {session && <Link href="/signals"><CTA big>前往黑潮船長信號</CTA></Link>}
          </div>
          <div style={{ fontSize: 12, color: C.dim, marginTop: 16 }}>不需信用卡 · 隨時可取消</div>
        </div>
      </section>
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: C.mut }}>{label}</span>
      <span style={{ fontFamily: MONO, color: color || C.ink, fontWeight: 700 }}>{value}</span>
    </div>
  );
}
function LockedRow({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: C.mut }}>{label}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 4, color: C.dim }}><Lock size={11} />登入解鎖</span>
    </div>
  );
}
