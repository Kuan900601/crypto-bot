"use client";
import { Star } from "lucide-react";
import { Ticker } from "@/lib/types";
import { useApp } from "@/lib/store";
import { fmtPrice, fmtPct } from "@/lib/format";
import Sparkline from "./Sparkline";
export default function PriceCard({ t }: { t: Ticker }) {
  const { watchlist, toggleWatch, setDetail } = useApp();
  const watched = watchlist.includes(t.symbol);
  const up = t.changePct >= 0;
  const bybit = t.class === "crypto" ? t.tvSymbol.replace("BYBIT:", "") : null;
  const open = () => setDetail({ symbol: t.symbol, name: t.name, type: t.class, tvSymbol: t.tvSymbol, bybit });
  return (
    <div onClick={open} className="group cursor-pointer rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 transition hover:border-tide-500/40 hover:bg-white/[0.04]">
      <div className="flex items-center gap-2">
        <span className="font-mono text-sm font-bold">{t.symbol}</span>
        <span className={`rounded px-1 py-0.5 text-[9px] ${t.class === "crypto" ? "bg-tide-500/15 text-tide-300" : "bg-amber-500/15 text-amber-300"}`}>
          {t.class === "crypto" ? "幣" : "股"}
        </span>
        <button onClick={(e) => { e.stopPropagation(); toggleWatch(t.symbol); }} className="ml-auto text-slate-500">
          <Star size={13} fill={watched ? "#e0bf5e" : "none"} className={watched ? "text-tide-400" : ""} />
        </button>
      </div>
      <div className="mt-2 flex items-end justify-between gap-2">
        <div>
          <div className="font-mono text-base font-semibold">${fmtPrice(t.price)}</div>
          <div className={`text-xs font-medium ${up ? "text-up" : "text-down"}`}>{fmtPct(t.changePct)}</div>
        </div>
        <div className="h-8 w-20 shrink-0"><Sparkline data={t.spark} up={up} /></div>
      </div>
    </div>
  );
}
