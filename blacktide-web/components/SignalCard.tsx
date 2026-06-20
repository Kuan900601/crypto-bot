"use client";
import { Signal } from "@/lib/types";
import { Badge, Card, Progress } from "./ui";
import { fmtPrice, entryGradeDisplay } from "@/lib/format";
import { TrendingUp, TrendingDown } from "lucide-react";
const TIER_TONE: Record<Signal["tier"], "amber" | "tide" | "slate"> = { S: "amber", A: "tide", B: "slate", C: "slate" };
const STATUS_LABEL: Record<Signal["status"], string> = { active: "進行中", tp: "已止盈", sl: "已止損", closed: "已平倉" };
const STATUS_TONE: Record<Signal["status"], "tide" | "up" | "down" | "slate"> = { active: "tide", tp: "up", sl: "down", closed: "slate" };
export default function SignalCard({ s, onOpen }: { s: Signal; onOpen: () => void }) {
  const long = s.direction === "long";
  return (
    <Card onClick={onOpen} className="cursor-pointer p-4 transition-colors hover:border-tide-500/30">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${long ? "bg-up/10 text-up" : "bg-down/10 text-down"}`}>
          {long ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
        </span>
        <span className="font-bold">{s.symbol}</span>
        <Badge tone={long ? "up" : "down"}>{long ? "做多" : "做空"}</Badge>
        <Badge tone={TIER_TONE[s.tier]}>Tier {s.tier}</Badge>
        <span className="ml-auto"><Badge tone={STATUS_TONE[s.status]}>{STATUS_LABEL[s.status]}</Badge></span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
        <div><div className="text-slate-500">進場區間</div><div className="mt-0.5 font-mono">{s.entryLow != null ? `${fmtPrice(s.entryLow)}–${fmtPrice(s.entryHigh)}` : "🔒 需升級"}</div></div>
        <div><div className="text-slate-500">止損</div><div className="mt-0.5 font-mono text-down">{s.stopLoss != null ? fmtPrice(s.stopLoss) : "🔒 需升級"}</div></div>
        <div><div className="text-slate-500">TP1{s.rr != null ? `（${s.rr}R）` : ""}</div><div className="mt-0.5 font-mono text-up">{s.tps?.[0]?.price != null ? fmtPrice(s.tps[0].price) : "🔒 需升級"}</div></div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
        <span>評分 {s.score}</span>
        <div className="w-16"><Progress value={s.score} /></div>
        <span>勝率（推算）{s.winRate}%</span>
        <span className="ml-auto">{entryGradeDisplay(s.entryGrade)}{s.leverage != null ? ` · ${s.leverage}x` : ""}</span>
      </div>
      {s.status !== "active" && s.finalPct !== undefined && (
        <div className={`mt-2 text-xs font-semibold ${s.finalPct >= 0 ? "text-up" : "text-down"}`}>
          結算 {s.finalPct >= 0 ? "+" : ""}{s.finalPct}%（分批止盈加權）
        </div>
      )}
    </Card>
  );
}
