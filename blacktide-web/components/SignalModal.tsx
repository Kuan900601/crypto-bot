"use client";
import { useState } from "react";
import { Signal } from "@/lib/types";
import { fmtPrice, entryGradeDisplay } from "@/lib/format";
import { C, MONO } from "@/lib/theme";
import Corner from "@/components/site/Corner";
import { X, Copy, Check, Lock } from "lucide-react";

export default function SignalModal({ s, onClose }: { s: Signal; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const long = s.direction === "long";
  const sc = long ? C.green : C.rose;
  const locked = s.entryLow == null;
  const copy = async () => {
    if (locked) return;
    const text = [
      `【黑潮信號】${s.symbol} ${long ? "做多" : "做空"}（Tier ${s.tier}）`,
      `進場：${fmtPrice(s.entryLow)} - ${fmtPrice(s.entryHigh)}`,
      `止損：${fmtPrice(s.stopLoss)}`,
      ...(s.tps ?? []).map((tp) => `TP${tp.level}：${fmtPrice(tp.price)}（${tp.r}R / 倉位 ${tp.weight}%）`),
      `槓桿：${s.leverage}x | AI 信心評分（推算）：${s.winRate}% | 進場品質：${entryGradeDisplay(s.entryGrade)}`,
    ].join("\n");
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch {}
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(2,4,9,0.7)", backdropFilter: "blur(5px)" }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="relative max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl p-5" style={{
        background: "linear-gradient(180deg, rgba(10,20,34,0.98), rgba(4,9,16,0.98))", border: `1px solid ${C.linePrimary}`, boxShadow: "0 30px 80px rgba(0,0,0,.5)",
      }}>
        <Corner pos="tl" /><Corner pos="tr" /><Corner pos="bl" /><Corner pos="br" />
        <div className="flex items-center gap-2">
          <span style={{ fontFamily: MONO, fontSize: 18, fontWeight: 800, color: C.ink }}>{s.symbol}</span>
          <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 9px", borderRadius: 99, color: sc, background: sc + "1A" }}>{long ? "做多" : "做空"}</span>
          <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 9px", borderRadius: 6, color: s.tier === "S" ? C.primary : C.mut, border: `1px solid ${s.tier === "S" ? C.primary + "55" : C.line}` }}>Tier {s.tier}</span>
          <span style={{ fontSize: 10.5, color: C.mut }}>{entryGradeDisplay(s.entryGrade)}</span>
          <button onClick={onClose} className="ml-auto ham rounded-lg p-1.5" style={{ color: C.mut }}><X size={18} /></button>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3" style={{ fontSize: 11.5 }}>
          <Cell label="進場區間" value={!locked ? `${fmtPrice(s.entryLow)}–${fmtPrice(s.entryHigh)}` : null} />
          <Cell label="止損" value={s.stopLoss != null ? fmtPrice(s.stopLoss) : null} color={C.rose} />
          <Cell label="槓桿" value={s.leverage != null ? `${s.leverage}x` : null} />
          <Cell label="開倉時間" value={s.openedAt || "-"} small />
        </div>

        <div className="mt-4">
          <div className="mb-1.5" style={{ fontSize: 12, fontWeight: 700, color: C.mut }}>分批止盈計畫</div>
          {(s.tps?.length ?? 0) > 0 ? (
            <div style={{ borderRadius: 12, overflow: "hidden", border: `1px solid ${C.line}` }}>
              {s.tps.map((tp) => (
                <div key={tp.level} className="flex items-center gap-3 px-3 py-2" style={{ fontSize: 11.5, borderBottom: `1px solid ${C.line}` }}>
                  <span style={{ width: 36, fontWeight: 700, color: C.ink }}>TP{tp.level}</span>
                  <span style={{ fontFamily: MONO, color: C.ink }}>{fmtPrice(tp.price)}</span>
                  <span style={{ color: C.dim }}>{tp.r}R</span>
                  <span style={{ color: C.dim }}>倉位 {tp.weight}%</span>
                  <span style={{ marginLeft: "auto", color: tp.hit ? C.green : C.dim }}>{tp.hit ? "已觸及" : "未觸及"}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-4" style={{ border: `1px solid ${C.line}`, fontSize: 11.5, color: C.dim }}>
              <Lock size={12} />鎖定 · 升級解鎖分批止盈計畫
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3" style={{ fontSize: 11.5, color: C.mut }}>
          <span>五維評分 <span style={{ fontFamily: MONO, color: C.ink }}>{s.score}</span>/100</span>
          <span>策略投票 <span style={{ fontFamily: MONO, color: C.ink }}>{s.votes}</span>/8</span>
          <span>新聞票：{s.newsVote === 1 ? "看多 +1" : s.newsVote === -1 ? "看空 +1" : "無"}</span>
        </div>
        {s.note && <div className="mt-2 rounded-lg px-3 py-2" style={{ background: "rgba(0,212,255,0.08)", fontSize: 11.5, color: C.primary }}>{s.note}</div>}
        {s.finalPct !== undefined && (
          <div className="mt-3" style={{ fontFamily: MONO, fontSize: 13.5, fontWeight: 700, color: s.finalPct >= 0 ? C.green : C.rose }}>
            歷史結算：{s.finalPct >= 0 ? "+" : ""}{s.finalPct}%（依倉位權重加權，與帳面浮盈不同屬正常）
          </div>
        )}
        <button onClick={copy} disabled={locked} className="cta mt-5 flex w-full items-center justify-center gap-2 rounded-xl py-3" style={{
          fontSize: 13.5, fontWeight: 700, color: locked ? C.dim : C.abyss,
          background: locked ? "rgba(255,255,255,0.04)" : `linear-gradient(135deg,#FFF4D2,${C.primary} 45%,${C.primary2})`,
          opacity: locked ? 1 : undefined, cursor: locked ? "not-allowed" : "pointer", animation: locked ? "none" : undefined,
        }}>
          {copied ? <Check size={15} /> : <Copy size={15} />}{copied ? "已複製" : locked ? "升級解鎖後可複製" : "複製完整下單計畫"}
        </button>
      </div>
    </div>
  );
}

function Cell({ label, value, color, small }: { label: string; value: string | null; color?: string; small?: boolean }) {
  return (
    <div className="rounded-lg p-2.5" style={{ background: "rgba(255,255,255,0.03)" }}>
      <div style={{ color: C.dim, fontSize: 10.5 }}>{label}</div>
      <div style={{ marginTop: 2, fontFamily: "ui-monospace,SF Mono,Menlo,monospace", fontSize: small ? 10.5 : 13, color: value ? (color || C.ink) : C.dim, display: "flex", alignItems: "center", gap: 4 }}>
        {value ?? <><Lock size={11} />鎖定</>}
      </div>
    </div>
  );
}
