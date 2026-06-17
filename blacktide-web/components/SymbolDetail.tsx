"use client";
import { useEffect, useState } from "react";
import { X, Star, Sparkles } from "lucide-react";
import { useApp } from "@/lib/store";
import { Badge, Progress } from "./ui";
import TradingViewChart from "./TradingViewChart";
import { fmtPrice, fmtPct, compactZh } from "@/lib/format";
interface Live { ok: boolean; price?: number; changePct?: number; high24h?: number; low24h?: number; volume?: number; funding?: number | null; oi?: number | null; }
interface AI {
  symbol: string; price: number; change24h: number; rsi: number; ma20: number; ma50: number; atrPct: number; momentum: number;
  fundingPct: number; trend: string; bias: string; confidence: number; risk: number; sentiment: number; support: number[]; resistance: number[]; basis: string[]; action: string;
}
const biasLabel = (b: string) => (b === "long" ? "看多" : b === "short" ? "看空" : "中性");
const biasTone = (b: string): "up" | "down" | "slate" => (b === "long" ? "up" : b === "short" ? "down" : "slate");
export default function SymbolDetail() {
  const { detail, setDetail, watchlist, toggleWatch } = useApp();
  const [live, setLive] = useState<Live | null>(null);
  const [ai, setAi] = useState<AI | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  useEffect(() => {
    setLive(null); setAi(null);
    if (!detail || detail.type !== "crypto" || !detail.bybit) return;
    let dead = false;
    const load = () => fetch("/api/ticker?symbol=" + detail.bybit).then((r) => r.json()).then((d) => { if (!dead) setLive(d); }).catch(() => {});
    load();
    const id = setInterval(load, 5000);
    setAiLoading(true);
    fetch("/api/coin?symbol=" + detail.bybit).then((r) => r.json()).then((d) => { if (!dead) { setAi(d.ok ? d.analysis : null); setAiLoading(false); } }).catch(() => { if (!dead) setAiLoading(false); });
    return () => { dead = true; clearInterval(id); };
  }, [detail]);
  if (!detail) return null;
  const watched = watchlist.includes(detail.symbol);
  const up = (live?.changePct ?? 0) >= 0;
  const cell = (label: string, value: string, cls = "") => (
    <div className="rounded-lg bg-white/[0.03] p-2 text-center"><div className="text-[10px] text-slate-500">{label}</div><div className={"mt-0.5 font-mono text-xs font-semibold " + cls}>{value}</div></div>
  );
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/75" onClick={() => setDetail(null)} />
      <div className="pop-in relative flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl border border-white/10 bg-ink-800 sm:rounded-2xl">
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
          {detail.type === "crypto" && (
            <div className="mb-3 rounded-xl border border-tide-500/15 bg-tide-500/[0.03] p-3">
              <div className="mb-2 flex items-center gap-2">
                <Sparkles size={15} className="text-tide-300" />
                <span className="text-sm font-semibold">AI 即時分析</span>
                {ai && <Badge tone={biasTone(ai.bias)}>{biasLabel(ai.bias)}</Badge>}
                <span className="ml-auto text-[10px] text-slate-500">技術指標 · 非投資建議</span>
              </div>
              {aiLoading && !ai && <div className="py-3 text-center text-xs text-slate-500">分析中…</div>}
              {!aiLoading && !ai && <div className="py-3 text-center text-xs text-slate-500">此標的暫無足夠資料分析</div>}
              {ai && (
                <div>
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                    {cell("RSI(14)", String(ai.rsi), ai.rsi >= 70 ? "text-down" : ai.rsi <= 30 ? "text-up" : "")}
                    {cell("趨勢", ai.trend === "up" ? "多頭" : ai.trend === "down" ? "空頭" : "盤整", ai.trend === "up" ? "text-up" : ai.trend === "down" ? "text-down" : "")}
                    {cell("ATR", ai.atrPct + "%")}
                    {cell("MA20", fmtPrice(ai.ma20))}
                    {cell("MA50", fmtPrice(ai.ma50))}
                    {cell("動能", (ai.momentum >= 0 ? "+" : "") + ai.momentum + "%", ai.momentum >= 0 ? "text-up" : "text-down")}
                  </div>
                  <div className="mt-3 space-y-2 text-xs">
                    <div className="flex items-center gap-2"><span className="w-12 shrink-0 text-slate-500">信心</span><Progress value={ai.confidence} /><span className="w-8 text-right text-slate-400">{ai.confidence}</span></div>
                    <div className="flex items-center gap-2"><span className="w-12 shrink-0 text-slate-500">風險</span><Progress value={ai.risk} tone={ai.risk >= 66 ? "down" : ai.risk >= 40 ? "amber" : "up"} /><span className="w-8 text-right text-slate-400">{ai.risk}</span></div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                    {ai.support.map((v, i) => <span key={"s" + i} className="rounded bg-up/10 px-2 py-0.5 text-up">支撐 {v}</span>)}
                    {ai.resistance.map((v, i) => <span key={"r" + i} className="rounded bg-down/10 px-2 py-0.5 text-down">壓力 {v}</span>)}
                  </div>
                  <div className="mt-3 rounded-lg bg-white/[0.03] p-2.5 text-xs leading-relaxed text-slate-300">
                    {ai.action}
                    <ul className="mt-2 space-y-1 text-[11px] text-slate-400">{ai.basis.map((b, i) => <li key={i}>· {b}</li>)}</ul>
                  </div>
                </div>
              )}
            </div>
          )}
          {detail.type === "stock" && (
            <div className="mb-3 text-xs text-slate-500">美股即時報價與指標請見下方圖表（TradingView）。</div>
          )}
          <TradingViewChart tvSymbol={detail.tvSymbol} height={380} />
        </div>
      </div>
    </div>
  );
}
