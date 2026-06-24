"use client";
import { Signal } from "@/lib/types";
import { fmtPrice, entryGradeDisplay } from "@/lib/format";
import { C, MONO } from "@/lib/theme";
import Corner from "@/components/site/Corner";
import { TrendingUp, TrendingDown, Lock } from "lucide-react";
import { useTilt } from "@/lib/useTilt";

const STATUS_LABEL: Record<Signal["status"], string> = { active: "進行中", tp: "已止盈", sl: "已止損", closed: "已平倉" };

/** 信號卡：locked 完全依 s.entryLow == null（後端 sanitizeSignal 是否放行）判斷，
 *  前端不做任何 tier 猜測或門檻判斷。 */
export default function SignalCard({ s, onOpen }: { s: Signal; onOpen: () => void }) {
  const long = s.direction === "long";
  const sc = long ? C.green : C.rose;
  const locked = s.entryLow == null;
  const tiltRef = useTilt<HTMLDivElement>(5);
  return (
    <div ref={tiltRef} onClick={onOpen} className="sigrow glass-sheen tilt-card" style={{
      cursor: "pointer", position: "relative", overflow: "hidden", padding: "16px 16px 14px 20px", borderRadius: 16,
      background: "linear-gradient(180deg, rgba(16,30,48,0.75), rgba(6,16,30,0.62))", border: `1px solid ${C.line}`,
    }}>
      <span className="accent-bar" style={{ background: `linear-gradient(${sc},transparent)`, boxShadow: `0 0 6px ${sc}` }} />
      <div className="row-sweep" />
      <Corner pos="tr" /><Corner pos="br" />
      <div className="flex flex-wrap items-center gap-2" style={{ position: "relative", zIndex: 1 }}>
        <span style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 26, height: 26, borderRadius: 9, color: sc, background: sc + "1A" }}>
          {long ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
        </span>
        <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 16, color: C.ink }}>{s.symbol}</span>
        <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 99, color: sc, background: sc + "1A" }}>{long ? "做多" : "做空"}</span>
        <span className="grade-pill" style={{ fontSize: 9.5, fontWeight: 700, padding: "2px 8px", borderRadius: 6, color: s.tier === "S" ? C.gold : C.mut, border: `1px solid ${s.tier === "S" ? C.gold + "55" : C.line}` }}>Tier {s.tier}</span>
        <span style={{ marginLeft: "auto", fontSize: 10.5, color: s.status === "active" ? C.teal : C.dim }}>{STATUS_LABEL[s.status]}</span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2" style={{ position: "relative", zIndex: 1, fontSize: 11.5 }}>
        <div><div style={{ color: C.dim }}>進場區間</div><div style={{ marginTop: 3, fontFamily: MONO, color: C.ink }}>{!locked ? `${fmtPrice(s.entryLow)}–${fmtPrice(s.entryHigh)}` : <LockedTag />}</div></div>
        <div><div style={{ color: C.dim }}>止損</div><div style={{ marginTop: 3, fontFamily: MONO, color: C.rose }}>{s.stopLoss != null ? fmtPrice(s.stopLoss) : <LockedTag />}</div></div>
        <div><div style={{ color: C.dim }}>TP1{s.rr != null ? `（${s.rr}R）` : ""}</div><div style={{ marginTop: 3, fontFamily: MONO, color: C.green }}>{s.tps?.[0]?.price != null ? fmtPrice(s.tps[0].price) : <LockedTag />}</div></div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5" style={{ position: "relative", zIndex: 1, fontSize: 11, color: C.mut }}>
        <SonarScore value={s.score} />
        <span>AI 信心評分（推算）{s.winRate}%</span>
        <span style={{ marginLeft: "auto" }}>{entryGradeDisplay(s.entryGrade)}{s.leverage != null ? ` · ${s.leverage}x` : ""}</span>
      </div>

      {s.status !== "active" && s.finalPct !== undefined && (
        <div style={{ position: "relative", zIndex: 1, marginTop: 8, fontSize: 12, fontWeight: 700, color: s.finalPct >= 0 ? C.green : C.rose, fontFamily: MONO }}>
          結算 {s.finalPct >= 0 ? "+" : ""}{s.finalPct}%（分批止盈加權）
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
