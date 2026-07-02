"use client";
import { Signal } from "@/lib/types";
import { fmtPrice, entryGradeDisplay } from "@/lib/format";
import { C, MONO } from "@/lib/theme";
import Corner from "@/components/site/Corner";
import { TrendingUp, TrendingDown, Lock } from "lucide-react";
import { useTilt } from "@/lib/useTilt";

const STATUS_LABEL: Record<Signal["status"], string> = { active: "進行中", tp: "已止盈", sl: "已止損", closed: "已平倉" };

const TIER_STYLE: Record<string, React.CSSProperties> = {
  S: { color: C.gold,    border: `1px solid ${C.gold}88`,   background: `${C.gold}22`          },
  A: { color: C.teal,    border: `1px solid ${C.teal}66`,   background: `${C.teal}18`          },
  B: { color: "#64748b", border: "1px solid #64748b55",     background: "rgba(100,116,139,0.1)" },
  C: { color: C.dim,     border: `1px solid ${C.line}`,     background: "transparent"           },
};

/** 信號卡：locked 完全依 s.entryLow == null（後端 sanitizeSignal 是否放行）判斷，
 *  前端不做任何 tier 猜測或門檻判斷。 */
export default function SignalCard({ s, onOpen }: { s: Signal; onOpen: () => void }) {
  const long = s.direction === "long";
  const sc = long ? C.green : C.rose;
  const locked = s.entryLow == null;
  const tiltRef = useTilt<HTMLDivElement>(5);
  const tierStyle = TIER_STYLE[s.tier] ?? TIER_STYLE["C"];

  return (
    <div ref={tiltRef} onClick={onOpen} className="sigrow glass-sheen tilt-card" style={{
      cursor: "pointer", position: "relative", overflow: "hidden", padding: "16px 16px 14px 20px", borderRadius: 16,
      background: "linear-gradient(180deg, rgba(16,30,48,0.75), rgba(6,16,30,0.62))", border: `1px solid ${C.line}`,
    }}>
      <span className="accent-bar" style={{ background: `linear-gradient(${sc},transparent)`, boxShadow: `0 0 6px ${sc}` }} />
      <div className="row-sweep" />
      <Corner pos="tr" /><Corner pos="br" />

      {/* ── 頂行：方向 / 幣種 / Tier pill / 狀態 ── */}
      <div className="flex flex-wrap items-center gap-2" style={{ position: "relative", zIndex: 1 }}>
        <span style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 26, height: 26, borderRadius: 9, color: sc, background: sc + "1A" }}>
          {long ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
        </span>
        <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 16, color: C.ink }}>{s.symbol}</span>
        <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 99, color: sc, background: sc + "1A" }}>{long ? "做多" : "做空"}</span>
        <span className="grade-pill" style={{ fontSize: 9.5, fontWeight: 700, padding: "2px 8px", borderRadius: 6, ...tierStyle }}>
          Tier {s.tier}
        </span>
        {/* 狀態：active 帶跳動 dot */}
        <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 5, fontSize: 10.5, color: s.status === "active" ? C.teal : C.dim }}>
          {s.status === "active" && <span className="pulse-live" />}
          {STATUS_LABEL[s.status]}
        </span>
      </div>

      {/* ── 進場區間 / 止損 / TP1 ── */}
      <div className="mt-3 grid grid-cols-3 gap-2" style={{ position: "relative", zIndex: 1, fontSize: 11.5 }}>
        <div><div style={{ color: C.dim }}>進場區間</div><div style={{ marginTop: 3, fontFamily: MONO, color: C.ink }}>{!locked ? `${fmtPrice(s.entryLow)}–${fmtPrice(s.entryHigh)}` : <LockedTag />}</div></div>
        <div><div style={{ color: C.dim }}>止損</div><div style={{ marginTop: 3, fontFamily: MONO, color: C.rose }}>{s.stopLoss != null ? fmtPrice(s.stopLoss) : <LockedTag />}</div></div>
        <div><div style={{ color: C.dim }}>TP1{s.rr != null ? `（${s.rr}R）` : ""}</div><div style={{ marginTop: 3, fontFamily: MONO, color: C.green }}>{s.tps?.[0]?.price != null ? fmtPrice(s.tps[0].price) : <LockedTag />}</div></div>
      </div>

      {/* ── 評分列 ── */}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5" style={{ position: "relative", zIndex: 1, fontSize: 11, color: C.mut }}>
        <SonarScore value={s.score} />
        <span>AI 信心評分（推算）{s.winRate}%</span>
        <span style={{ marginLeft: "auto" }}>{entryGradeDisplay(s.entryGrade)}{s.leverage != null ? ` · ${s.leverage}x` : ""}</span>
      </div>

      {/* ── 結算結果（大字 chip） ── */}
      {s.status !== "active" && s.finalPct !== undefined && (
        <div style={{ position: "relative", zIndex: 1, marginTop: 10, display: "inline-flex", alignItems: "baseline", gap: 5,
          padding: "5px 12px", borderRadius: 10,
          background: s.finalPct >= 0 ? `${C.green}20` : `${C.rose}20`,
          border: `1px solid ${s.finalPct >= 0 ? C.green : C.rose}44`,
        }}>
          <span style={{ fontFamily: MONO, fontSize: 20, fontWeight: 800, lineHeight: 1, color: s.finalPct >= 0 ? C.green : C.rose }}>
            {s.finalPct >= 0 ? "+" : ""}{s.finalPct}%
          </span>
          <span style={{ fontSize: 10, color: C.dim }}>加權結算</span>
        </div>
      )}
    </div>
  );
}

function LockedTag() {
  return <span className="locked-px" style={{ display: "inline-flex", alignItems: "center", gap: 3, letterSpacing: 1 }}><Lock size={10} />鎖定</span>;
}

/** 五維評分目前後端只回單一綜合分數（score），沒有逐維拆解資料，
 *  所以用聲納環呈現「整體評分」，不偽造五個維度的假數字。 */
function SonarScore({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ position: "relative", width: 16, height: 16, flexShrink: 0 }}>
        <span style={{ position: "absolute", inset: 0, borderRadius: "50%", border: `1.5px solid ${C.line}` }} />
        <svg width="16" height="16" viewBox="0 0 16 16" style={{ position: "absolute", inset: 0, transform: "rotate(-90deg)" }}>
          <circle cx="8" cy="8" r="6.4" fill="none" stroke={C.gold} strokeWidth="2.2" strokeDasharray={`${(pct / 100) * 40.2} 40.2`} strokeLinecap="round" />
        </svg>
      </span>
      評分 <span style={{ fontFamily: MONO, color: C.ink }}>{value}</span>/100
    </span>
  );
}
