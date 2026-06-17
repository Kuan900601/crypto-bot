"use client";
import { useEffect, useState } from "react";
import { X, Star, Sparkles } from "lucide-react";
import { useApp } from "@/lib/store";
import { Badge } from "./ui";
import TradingViewChart from "./TradingViewChart";
import { fmtPrice, fmtPct, compactZh } from "@/lib/format";
interface Live { ok: boolean; price?: number; changePct?: number; high24h?: number; low24h?: number; volume?: number; funding?: number | null; oi?: number | null; }
interface AI {
  symbol: string; price: number; change24h: number; rsi: number; ma20: number; ma50: number; atrPct: number; momentum: number;
  fundingPct: number; trend: string; bias: string; confidence: number; risk: number; sentiment: number;
  oi?: number | null; support: number[]; resistance: number[]; basis: string[]; action: string;
}
const biasLabel = (b: string) => (b === "long" ? "偏多看漲" : b === "short" ? "偏空看跌" : "中性整理");
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
    <div className="rounded-lg bg-white/[0.03] p-2 text-center">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={"mt-0.5 font-mono text-xs font-semibold " + cls}>{value}</div>
    </div>
  );
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/75" onClick={() => setDetail(null)} />
      <div className="pop-in relative flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl border border-white/10 bg-ink-800 sm:rounded-2xl">
        {/* Header */}
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
          {/* Live price stats */}
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
                    <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-500">24h 成交量</div><div className="mt-0.5 font-mono">${compactZh(live.volume || 0)}</div></div>
                    <div className="rounded-lg bg-white/[0.03] p-2">
                      <div className="text-slate-500">資金費率</div>
                      <div className={`mt-0.5 font-mono ${live.funding != null && live.funding > 0.0005 ? "text-amber-400" : live.funding != null && live.funding < -0.0001 ? "text-blue-400" : ""}`}>
                        {live.funding != null ? (live.funding * 100).toFixed(4) + "%" : "-"}
                      </div>
                    </div>
                  </div>
                  {live.oi != null && (
                    <div className="mt-1.5 flex items-center rounded-lg bg-white/[0.02] px-3 py-2 text-xs">
                      <span className="text-slate-500">未平倉量 OI</span>
                      <span className="ml-auto font-mono text-slate-300">${compactZh(live.oi)}</span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-xs text-slate-500">即時資料載入中…</div>
              )}
            </div>
          )}
          {/* AI Analysis Panel */}
          {detail.type === "crypto" && (
            <div className="mb-3 rounded-xl border border-tide-500/15 bg-tide-500/[0.03] p-3">
              <div className="mb-3 flex items-center gap-2">
                <Sparkles size={15} className="text-tide-300" />
                <span className="text-sm font-semibold">AI 即時分析</span>
                {ai && <Badge tone={biasTone(ai.bias)}>{biasLabel(ai.bias)}</Badge>}
                <span className="ml-auto text-[10px] text-slate-500">技術指標 · 非投資建議</span>
              </div>
              {aiLoading && !ai && <div className="py-3 text-center text-xs text-slate-500">分析中…</div>}
              {!aiLoading && !ai && <div className="py-3 text-center text-xs text-slate-500">此標的暫無足夠資料分析</div>}
              {ai && (
                <div className="space-y-2">
                  {/* Verdict banner */}
                  <div className={`flex items-center gap-4 rounded-xl border px-4 py-3 ${ai.bias === "long" ? "border-up/20 bg-up/[0.07]" : ai.bias === "short" ? "border-down/20 bg-down/[0.07]" : "border-white/10 bg-white/[0.02]"}`}>
                    <div>
                      <div className="text-[10px] uppercase tracking-widest text-slate-500">AI 綜合判斷</div>
                      <div className={`mt-0.5 font-display text-2xl font-bold ${ai.bias === "long" ? "text-up" : ai.bias === "short" ? "text-down" : "text-slate-200"}`}>
                        {biasLabel(ai.bias)}
                      </div>
                    </div>
                    <div className="ml-auto text-right">
                      <div className="text-[10px] text-slate-500">信心 / 風險</div>
                      <div className="font-mono text-base font-bold">
                        {ai.confidence}<span className="text-[10px] font-normal text-slate-500">%</span>
                        {" / "}
                        <span className={ai.risk >= 66 ? "text-down" : ai.risk >= 40 ? "text-amber-400" : "text-up"}>{ai.risk}</span>
                      </div>
                    </div>
                  </div>
                  {/* Key indicators 6-grid */}
                  <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-6">
                    {cell("RSI(14)", String(ai.rsi), ai.rsi >= 70 ? "text-down" : ai.rsi <= 30 ? "text-up" : "")}
                    {cell("趨勢", ai.trend === "up" ? "多頭排列" : ai.trend === "down" ? "空頭排列" : "均線糾結", ai.trend === "up" ? "text-up" : ai.trend === "down" ? "text-down" : "")}
                    {cell("ATR 波動", ai.atrPct + "%", ai.atrPct > 3 ? "text-amber-400" : "")}
                    {cell("動能 24h", (ai.momentum >= 0 ? "+" : "") + ai.momentum + "%", ai.momentum >= 0 ? "text-up" : "text-down")}
                    {cell("資金費率", (ai.fundingPct >= 0 ? "+" : "") + ai.fundingPct.toFixed(3) + "%", Math.abs(ai.fundingPct) > 0.05 ? "text-amber-400" : "")}
                    {cell("市場情緒", ai.sentiment >= 60 ? "偏樂觀" : ai.sentiment <= 40 ? "偏悲觀" : "中性", ai.sentiment >= 60 ? "text-up" : ai.sentiment <= 40 ? "text-down" : "text-slate-400")}
                  </div>
                  {/* OI */}
                  {ai.oi != null && (
                    <div className="flex items-center rounded-lg bg-white/[0.03] px-3 py-2 text-xs">
                      <span className="text-slate-500">未平倉量 OI（分析時點）</span>
                      <span className="ml-auto font-mono font-semibold text-slate-300">${compactZh(ai.oi)}</span>
                    </div>
                  )}
                  {/* Support / Resistance */}
                  <div className="grid grid-cols-2 gap-1.5 text-xs">
                    <div className="rounded-lg bg-up/[0.06] px-3 py-2">
                      <div className="text-[10px] text-slate-500">支撐參考</div>
                      <div className="mt-0.5 font-mono font-bold text-up">{ai.support.map((v) => fmtPrice(v)).join(" / ")}</div>
                    </div>
                    <div className="rounded-lg bg-down/[0.06] px-3 py-2">
                      <div className="text-[10px] text-slate-500">壓力參考</div>
                      <div className="mt-0.5 font-mono font-bold text-down">{ai.resistance.map((v) => fmtPrice(v)).join(" / ")}</div>
                    </div>
                  </div>
                  {/* Integrated conclusion - terminal style */}
                  <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 text-xs">
                    <div className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-500">操作建議</div>
                    <div className="leading-relaxed text-slate-200">{ai.action}</div>
                    <div className="mt-2 space-y-1 border-t border-white/[0.06] pt-2 text-[11px] text-slate-500">
                      {ai.basis.map((b, i) => <div key={i}>· {b}</div>)}
                    </div>
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
