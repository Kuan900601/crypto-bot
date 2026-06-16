"use client";
import { useEffect, useState } from "react";
import { ANALYSES } from "@/lib/mock";
import { SectionTitle, Card, Badge, Progress } from "@/components/ui";
import { fmtPrice } from "@/lib/format";
import { X } from "lucide-react";
interface RA {
  symbol: string; price: number; change24h: number; rsi: number; ma20: number; ma50: number;
  atrPct: number; momentum: number; fundingPct: number; trend: string; bias: string;
  confidence: number; risk: number; sentiment: number; support: number[]; resistance: number[];
  basis: string[]; action: string;
}
const biasLabel = (b: string) => (b === "long" ? "看多" : b === "short" ? "看空" : "中性");
const biasTone = (b: string): "up" | "down" | "slate" => (b === "long" ? "up" : b === "short" ? "down" : "slate");
const trendZh = (t: string) => (t === "up" ? "多頭排列" : t === "down" ? "空頭排列" : "均線糾纏");
function DetailModal({ a, onClose }: { a: RA; onClose: () => void }) {
  const cell = (label: string, value: string, cls = "") => (
    <div className="rounded-lg bg-white/[0.03] p-2.5 text-center">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={"mt-0.5 font-mono text-sm " + cls}>{value}</div>
    </div>
  );
  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-t-2xl border border-white/10 bg-ink-800 p-5 sm:rounded-2xl">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold">{a.symbol}</span>
          <Badge tone={biasTone(a.bias)}>{biasLabel(a.bias)}</Badge>
          <span className="font-mono text-sm text-slate-300">${fmtPrice(a.price)}</span>
          <span className={"font-mono text-xs " + (a.change24h >= 0 ? "text-up" : "text-down")}>{a.change24h >= 0 ? "+" : ""}{a.change24h}%</span>
          <button onClick={onClose} className="ml-auto rounded-lg p-1.5 text-slate-400 hover:bg-white/5"><X size={18} /></button>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2">
          {cell("RSI(14)", String(a.rsi), a.rsi >= 70 ? "text-down" : a.rsi <= 30 ? "text-up" : "")}
          {cell("趨勢", trendZh(a.trend), a.trend === "up" ? "text-up" : a.trend === "down" ? "text-down" : "")}
          {cell("ATR 波動", a.atrPct + "%")}
          {cell("MA20", fmtPrice(a.ma20))}
          {cell("MA50", fmtPrice(a.ma50))}
          {cell("24h 動能", (a.momentum >= 0 ? "+" : "") + a.momentum + "%", a.momentum >= 0 ? "text-up" : "text-down")}
          {cell("資金費率", a.fundingPct + "%")}
          {cell("情緒", a.sentiment + "/100")}
          {cell("風險", String(a.risk), a.risk >= 60 ? "text-down" : "")}
        </div>
        <div className="mt-4 space-y-2 text-xs">
          <div className="flex items-center gap-2"><span className="w-12 shrink-0 text-slate-500">信心</span><div className="flex-1"><Progress value={a.confidence} /></div><span className="w-8 text-right font-mono">{a.confidence}</span></div>
          <div className="flex items-center gap-2"><span className="w-12 shrink-0 text-slate-500">風險</span><div className="flex-1"><Progress value={a.risk} tone={a.risk >= 60 ? "down" : "tide"} /></div><span className="w-8 text-right font-mono">{a.risk}</span></div>
          <div className="flex items-center gap-2"><span className="w-12 shrink-0 text-slate-500">情緒</span><div className="flex-1"><Progress value={a.sentiment} tone={a.sentiment >= 55 ? "up" : a.sentiment <= 45 ? "down" : "tide"} /></div><span className="w-8 text-right font-mono">{a.sentiment}</span></div>
        </div>
        <div className="mt-4 flex flex-wrap gap-1.5 text-[11px]">
          {a.support.map((v, i) => <span key={"s" + i} className="rounded bg-up/10 px-1.5 py-0.5 font-mono text-up">支 {fmtPrice(v)}</span>)}
          {a.resistance.map((v, i) => <span key={"r" + i} className="rounded bg-down/10 px-1.5 py-0.5 font-mono text-down">壓 {fmtPrice(v)}</span>)}
        </div>
        <div className="mt-4 rounded-lg bg-white/[0.03] p-3 text-xs leading-relaxed"><span className="font-semibold text-tide-300">操作建議：</span>{a.action}</div>
        <div className="mt-3">
          <div className="text-xs font-semibold text-slate-300">判讀依據</div>
          <ul className="mt-1.5 space-y-1 text-[11px] text-slate-400">
            {a.basis.map((b, i) => <li key={i} className="flex gap-1.5"><span className="text-tide-500">·</span>{b}</li>)}
          </ul>
        </div>
        <div className="mt-3 text-[10px] leading-relaxed text-slate-600">以上為技術指標即時計算結果，僅供參考，不構成投資建議。</div>
      </div>
    </div>
  );
}
export default function AnalysisPage() {
  const [ra, setRa] = useState<RA[] | null>(null);
  const [sel, setSel] = useState<RA | null>(null);
  useEffect(() => {
    fetch("/api/analysis").then((r) => r.json()).then((d) => setRa(d.analyses || [])).catch(() => setRa([]));
  }, []);
  const loading = ra === null;
  const real = ra && ra.length > 0 ? ra : null;
  const avg = real
    ? Math.round(real.reduce((a, x) => a + x.sentiment, 0) / real.length)
    : Math.round(ANALYSES.reduce((a, x) => a + x.sentiment, 0) / ANALYSES.length);
  return (
    <div className="space-y-5">
      <SectionTitle title="AI 智能分析"
        desc={real ? "技術指標即時計算（Bybit）· 點擊任一卡片看完整分析 · 非投資建議" : "技術指標分析 · 非投資建議"} />
      <Card className="p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold">市場綜合情緒</span>
          <span className="font-mono">{avg}/100</span>
        </div>
        <div className="mt-2"><Progress value={avg} tone={avg >= 55 ? "up" : avg <= 45 ? "down" : "tide"} /></div>
        <div className="mt-1.5 text-xs text-slate-500">{avg >= 55 ? "偏多" : avg <= 45 ? "偏空" : "中性"}</div>
      </Card>
      {loading && <div className="grid gap-4 lg:grid-cols-2">{[0, 1, 2, 3].map((i) => <Card key={i} className="h-52 animate-pulse" />)}</div>}
      {!loading && real && (
        <div className="grid gap-4 lg:grid-cols-2">
          {real.map((a) => (
            <Card key={a.symbol} onClick={() => setSel(a)} className="cursor-pointer p-4 transition hover:border-tide-500/30">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-bold">{a.symbol}</span>
                <Badge tone={biasTone(a.bias)}>{biasLabel(a.bias)}</Badge>
                <span className="font-mono text-xs text-slate-400">${fmtPrice(a.price)}</span>
                <span className={`font-mono text-xs ${a.change24h >= 0 ? "text-up" : "text-down"}`}>{a.change24h >= 0 ? "+" : ""}{a.change24h}%</span>
                <span className="ml-auto text-[10px] text-tide-300">詳情 →</span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-[11px]">
                <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-500">RSI</div><div className="mt-0.5 font-mono">{a.rsi}</div></div>
                <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-500">ATR%</div><div className="mt-0.5 font-mono">{a.atrPct}</div></div>
                <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-500">費率%</div><div className="mt-0.5 font-mono">{a.fundingPct}</div></div>
              </div>
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex items-center gap-2"><span className="w-12 shrink-0 text-slate-500">信心</span><div className="flex-1"><Progress value={a.confidence} /></div><span className="w-8 text-right font-mono">{a.confidence}</span></div>
                <div className="flex items-center gap-2"><span className="w-12 shrink-0 text-slate-500">風險</span><div className="flex-1"><Progress value={a.risk} tone={a.risk >= 60 ? "down" : "tide"} /></div><span className="w-8 text-right font-mono">{a.risk}</span></div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                {a.support.map((v, i) => <span key={"s" + i} className="rounded bg-up/10 px-1.5 py-0.5 font-mono text-up">支 {fmtPrice(v)}</span>)}
                {a.resistance.map((v, i) => <span key={"r" + i} className="rounded bg-down/10 px-1.5 py-0.5 font-mono text-down">壓 {fmtPrice(v)}</span>)}
              </div>
            </Card>
          ))}
        </div>
      )}
      {!loading && !real && (
        <>
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-xs text-amber-200">即時指標暫時無法取得，以下為展示資料。</div>
          <div className="grid gap-4 lg:grid-cols-2">
            {ANALYSES.map((a) => (
              <Card key={a.symbol} className="p-4">
                <div className="flex items-center gap-2">
                  <span className="font-bold">{a.symbol}</span>
                  <Badge tone={a.bias === "long" ? "up" : a.bias === "short" ? "down" : "slate"}>{biasLabel(a.bias)}</Badge>
                  <span className="ml-auto text-xs text-slate-500">風險 <span className={a.risk >= 60 ? "text-down" : "text-slate-300"}>{a.risk}</span></span>
                </div>
                <div className="mt-3 space-y-2 text-xs">
                  <div className="flex items-center gap-2"><span className="w-14 shrink-0 text-slate-500">信心指數</span><div className="flex-1"><Progress value={a.confidence} /></div><span className="w-8 text-right font-mono">{a.confidence}</span></div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                  {a.support.map((v) => <span key={"s" + v} className="rounded bg-up/10 px-1.5 py-0.5 font-mono text-up">支 {fmtPrice(v)}</span>)}
                  {a.resistance.map((v) => <span key={"r" + v} className="rounded bg-down/10 px-1.5 py-0.5 font-mono text-down">壓 {fmtPrice(v)}</span>)}
                </div>
                <div className="mt-3 rounded-lg bg-white/[0.03] p-2.5 text-xs leading-relaxed"><span className="font-semibold text-tide-300">建議：</span>{a.action}
                  <ul className="mt-2 space-y-1 text-[11px] text-slate-400">{a.basis.map((b, i) => <li key={i} className="flex gap-1.5"><span className="text-tide-500">·</span>{b}</li>)}</ul>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
      {sel && <DetailModal a={sel} onClose={() => setSel(null)} />}
    </div>
  );
}
