"use client";
import { useState } from "react";
import { Signal } from "@/lib/types";
import { Badge } from "./ui";
import { fmtPrice, entryGradeDisplay } from "@/lib/format";
import { X, Copy, Check } from "lucide-react";
export default function SignalModal({ s, onClose }: { s: Signal; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const long = s.direction === "long";
  const locked = s.entryLow == null;
  const copy = async () => {
    if (locked) return;
    const text = [
      `【黑潮信號】${s.symbol} ${long ? "做多" : "做空"}（Tier ${s.tier}）`,
      `進場：${fmtPrice(s.entryLow)} - ${fmtPrice(s.entryHigh)}`,
      `止損：${fmtPrice(s.stopLoss)}`,
      ...(s.tps ?? []).map((tp) => `TP${tp.level}：${fmtPrice(tp.price)}（${tp.r}R / 倉位 ${tp.weight}%）`),
      `槓桿：${s.leverage}x | 勝率（推算）：${s.winRate}% | 進場品質：${entryGradeDisplay(s.entryGrade)}`,
    ].join("\n");
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch {}
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-white/10 bg-ink-800 p-5">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold">{s.symbol}</span>
          <Badge tone={long ? "up" : "down"}>{long ? "做多" : "做空"}</Badge>
          <Badge tone={s.tier === "S" ? "amber" : "tide"}>Tier {s.tier}</Badge>
          <Badge>{entryGradeDisplay(s.entryGrade)}</Badge>
          <button onClick={onClose} className="ml-auto rounded-lg p-1.5 text-slate-400 hover:bg-white/5"><X size={18} /></button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-lg bg-white/[0.03] p-2.5"><div className="text-slate-500">進場區間</div><div className="mt-0.5 font-mono">{!locked ? `${fmtPrice(s.entryLow)}–${fmtPrice(s.entryHigh)}` : "🔒 升級解鎖"}</div></div>
          <div className="rounded-lg bg-white/[0.03] p-2.5"><div className="text-slate-500">止損</div><div className="mt-0.5 font-mono text-down">{s.stopLoss != null ? fmtPrice(s.stopLoss) : "🔒 升級解鎖"}</div></div>
          <div className="rounded-lg bg-white/[0.03] p-2.5"><div className="text-slate-500">槓桿</div><div className="mt-0.5 font-mono">{s.leverage != null ? `${s.leverage}x` : "🔒 升級解鎖"}</div></div>
          <div className="rounded-lg bg-white/[0.03] p-2.5"><div className="text-slate-500">開倉時間</div><div className="mt-0.5 font-mono text-[11px]">{s.openedAt || "-"}</div></div>
        </div>
        <div className="mt-4">
          <div className="mb-1.5 text-xs font-semibold text-slate-400">分批止盈計畫</div>
          {(s.tps?.length ?? 0) > 0 ? (
            <div className="overflow-hidden rounded-lg border border-white/5">
              {s.tps.map((tp) => (
                <div key={tp.level} className="flex items-center gap-3 border-b border-white/5 px-3 py-2 text-xs last:border-0">
                  <span className="w-9 font-semibold">TP{tp.level}</span>
                  <span className="font-mono">{fmtPrice(tp.price)}</span>
                  <span className="text-slate-500">{tp.r}R</span>
                  <span className="text-slate-500">倉位 {tp.weight}%</span>
                  <span className={`ml-auto ${tp.hit ? "text-up" : "text-slate-600"}`}>{tp.hit ? "已觸及" : "未觸及"}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-4 text-center text-xs text-slate-500">🔒 升級解鎖分批止盈計畫</div>
          )}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-400">
          <span>五維評分 <span className="font-mono text-slate-200">{s.score}</span>/100</span>
          <span>策略投票 <span className="font-mono text-slate-200">{s.votes}</span>/8</span>
          <span>新聞票：{s.newsVote === 1 ? "看多 +1" : s.newsVote === -1 ? "看空 +1" : "無"}</span>
        </div>
        {s.note && <div className="mt-2 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-200">{s.note}</div>}
        {s.finalPct !== undefined && (
          <div className={`mt-3 text-sm font-semibold ${s.finalPct >= 0 ? "text-up" : "text-down"}`}>
            歷史結算：{s.finalPct >= 0 ? "+" : ""}{s.finalPct}%（依倉位權重加權，與帳面浮盈不同屬正常）
          </div>
        )}
        <button onClick={copy} disabled={locked} className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-tide-500/15 py-2.5 text-sm font-semibold text-tide-300 hover:bg-tide-500/25 disabled:opacity-40">
          {copied ? <Check size={15} /> : <Copy size={15} />}{copied ? "已複製" : locked ? "升級解鎖後可複製" : "複製完整下單計畫"}
        </button>
      </div>
    </div>
  );
}
