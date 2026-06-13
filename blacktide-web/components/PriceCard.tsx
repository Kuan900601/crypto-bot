"use client";
import { useEffect, useRef, useState } from "react";
import { Star } from "lucide-react";
import Sparkline from "./Sparkline";
import { Card } from "./ui";
import { Ticker } from "@/lib/types";
import { fmtPrice, fmtPct, compactZh } from "@/lib/format";
import { useApp } from "@/lib/store";
export default function PriceCard({ t }: { t: Ticker }) {
  const { watchlist, toggleWatch, selectedSymbol, setSymbol } = useApp();
  const prev = useRef(t.price);
  const [flash, setFlash] = useState("");
  useEffect(() => {
    if (t.price > prev.current) setFlash("flash-up");
    else if (t.price < prev.current) setFlash("flash-down");
    prev.current = t.price;
    const id = setTimeout(() => setFlash(""), 600);
    return () => clearTimeout(id);
  }, [t.price]);
  const up = t.changePct >= 0;
  const watched = watchlist.includes(t.symbol);
  const selected = selectedSymbol === t.symbol;
  return (
    <Card onClick={() => setSymbol(t.symbol)}
      className={`cursor-pointer p-3 transition-all hover:border-tide-500/40 hover:shadow-[0_6px_24px_rgba(212,175,55,0.08)] ${selected ? "border-tide-500/40 ring-1 ring-tide-500/20" : ""}`}>
      <div className="flex items-center justify-between gap-1">
        <div className="min-w-0 truncate">
          <span className="text-[13px] font-bold">{t.symbol}</span>
          <span className="ml-1.5 hidden text-[10px] text-slate-500 min-[420px]:inline">{t.name}</span>
        </div>
        <button onClick={(e) => { e.stopPropagation(); toggleWatch(t.symbol); }} className="shrink-0">
          <Star size={14} fill={watched ? "#e0bf5e" : "none"} className={watched ? "text-tide-400" : "text-slate-600"} />
        </button>
      </div>
      <div className="mt-1.5 flex items-end justify-between gap-2">
        <div className="min-w-0">
          <div className={`truncate font-mono text-[15px] font-bold md:text-lg ${flash}`}>${fmtPrice(t.price)}</div>
          <div className={`text-xs font-medium ${up ? "text-up" : "text-down"}`}>{fmtPct(t.changePct)}</div>
        </div>
        <Sparkline data={t.spark} up={up} width={72} height={28} />
      </div>
      <div className="mt-2 flex justify-between text-[10px] text-slate-500">
        <span>量 {compactZh(t.volume)}</span>
        {t.fundingRate !== undefined
          ? <span>費率 {(t.fundingRate * 100).toFixed(3)}%</span>
          : t.marketCap ? <span>市值 {compactZh(t.marketCap)}</span> : null}
      </div>
    </Card>
  );
}
