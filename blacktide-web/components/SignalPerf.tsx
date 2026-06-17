"use client";
import { useEffect, useState } from "react";
import { Card, Stat } from "@/components/ui";
import { Signal } from "@/lib/types";
export default function SignalPerf() {
  const [sig, setSig] = useState<Signal[] | null>(null);
  useEffect(() => { fetch("/api/signals").then((r) => r.json()).then((d) => setSig(d.signals)).catch(() => {}); }, []);
  const closed = (sig || []).filter((s) => s.status !== "active" && s.finalPct !== undefined);
  const wins = closed.filter((s) => (s.finalPct ?? 0) > 0).length;
  const winRate = closed.length ? Math.round((wins / closed.length) * 100) : 0;
  const ev = closed.length ? closed.reduce((a, s) => a + (s.finalPct ?? 0), 0) / closed.length : 0;
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">黑潮船長 · 訊號績效 <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-normal text-slate-400">僅後台可見</span></div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="信號總數" value={String((sig || []).length)} />
        <Stat label="已結算" value={String(closed.length)} />
        <Stat label="已結算勝率" value={winRate + "%"} sub={wins + "/" + closed.length + " 筆"} />
        <Stat label="平均期望值" value={(ev >= 0 ? "+" : "") + ev.toFixed(2) + "%"} tone={ev >= 0 ? "up" : "down"} />
      </div>
    </Card>
  );
}
