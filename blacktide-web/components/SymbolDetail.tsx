"use client";
import { useEffect, useState } from "react";
import { X, Star } from "lucide-react";
import { useApp } from "@/lib/store";
import { Badge } from "./ui";
import TradingViewChart from "./TradingViewChart";
import { fmtPrice, fmtPct, compactZh } from "@/lib/format";
interface Live {
  ok: boolean; price?: number; changePct?: number; high24h?: number; low24h?: number;
  volume?: number; funding?: number | null; oi?: number | null;
}
export default function SymbolDetail() {
  const { detail, setDetail, watchlist, toggleWatch } = useApp();
  const [live, setLive] = useState<Live | null>(null);
  useEffect(() => {
    setLive(null);
    if (!detail || detail.type !== "crypto" || !detail.bybit) return;
    let dead = false;
    const load = () =>
      fetch("/api/ticker?symbol=" + detail.bybit).then((r) => r.json()).then((d) => { if (!dead) setLive(d); }).catch(() => {});
    load();
    const id = setInterval(load, 5000);
    return () => { dead = true; clearInterval(id); };
  }, [detail]);
  if (!detail) return null;
  const watched = watchlist.includes(detail.symbol);
  const up = (live?.changePct ?? 0) >= 0;
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/75" onClick={() => setDetail(null)} />
      <div className="relative flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl border border-white/10 bg-ink-800 sm:rounded-2xl">
        <div className="flex items-center gap-2 border-b border-white/5 px-4 py-3">
          <span className="font-display text-base font-bold">{detail.symbol}</span>
          <span className="text-xs text-slate-500">{detail.name}</span>
          <Badge tone={detail.type === "crypto" ? "tide" : "amber"}>{detail.type === "crypto" ? "加密" : "美股"}</Badge>
          <button onClick={() => toggleWatch(detail.symbol)} className="ml-auto text-slate-500">
            <Star size={16} fill={watched ? "#e0bf5e" : "none"} className={watched ? "text-tide-400" : ""} />
          </button>
          <button onClick={() => setDetail(null)} className="rounded-lg p-1 text-slate-400 hover:bg-white/5"><X size={18} /></button>
        </div>
        <div className="overflow-y-auto p-4">
          {detail.type === "crypto" && (
            <div className="mb-3">
              {live?.ok ? (
                <div>
                  <div className="flex items-end gap-3">
                    <span className="font-mono text-2xl font-bold">${fmtPrice(live.price || 0)}</span>
                    <span className={`pb-1 text-sm font-semibold ${up ? "text-up" : "text-down"}`}>{fmtPct(live.changePct || 0)}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                    <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-500">24h 高</div><div className="mt-0.5 font-mono">${fmtPrice(live.high24h || 0)}</div></div>
                    <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-500">24h 低</div><div className="mt-0.5 font-mono">${fmtPrice(live.low24h || 0)}</div></div>
                    <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-500">24h 量</div><div className="mt-0.5 font-mono">${compactZh(live.volume || 0)}</div></div>
                    <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-500">資金費率</div><div className="mt-0.5 font-mono">{live.funding != null ? (live.funding * 100).toFixed(4) + "%" : "-"}</div></div>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-slate-500">即時資料載入中…</div>
              )}
            </div>
          )}
          {detail.type === "stock" && (
            <div className="mb-3 text-xs text-slate-500">美股即時報價與指標請見下方圖表（TradingView）。</div>
          )}
          <TradingViewChart tvSymbol={detail.tvSymbol} height={420} />
        </div>
      </div>
    </div>
  );
}
