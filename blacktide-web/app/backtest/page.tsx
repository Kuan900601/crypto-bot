"use client";
import { useState } from "react";
import { SectionTitle, Card, Stat } from "@/components/ui";
import { makeRng } from "@/lib/format";
const SYMBOLS = ["BTC", "ETH", "SOL", "NVDA", "TSLA"];
const TFS = ["15m", "1h", "4h", "1d"];
const STRATS = ["黑潮綜合（7+1 投票）", "趨勢追隨", "動量策略", "BOS 突破"];
const PERIODS = [90, 180, 365];
interface Result { eq: number[]; maxDD: number; totalRet: number; winRate: number; trades: number; pf: number; sharpe: number; }
function runBacktest(seedStr: string): Result {
  let seed = 0;
  for (const c of seedStr) seed = (seed * 31 + c.charCodeAt(0)) | 0;
  const r = makeRng(seed);
  const n = 120;
  const eq: number[] = [100];
  const drift = (r() - 0.42) * 0.004;
  for (let i = 1; i < n; i++) eq.push(Math.max(20, eq[i - 1] * (1 + drift + (r() - 0.5) * 0.02)));
  let peak = eq[0], maxDD = 0;
  for (const v of eq) { peak = Math.max(peak, v); maxDD = Math.max(maxDD, (peak - v) / peak); }
  const totalRet = eq[n - 1] / 100 - 1;
  return {
    eq, maxDD: +(maxDD * 100).toFixed(1), totalRet: +(totalRet * 100).toFixed(1),
    winRate: Math.round(38 + r() * 24), trades: Math.round(40 + r() * 120),
    pf: +(0.8 + r() * 0.9).toFixed(2), sharpe: +((totalRet > 0 ? 0.4 : -0.2) + r() * 1.2).toFixed(2),
  };
}
function EquityChart({ eq }: { eq: number[] }) {
  const w = 560, h = 200;
  const min = Math.min(...eq), max = Math.max(...eq), span = max - min || 1;
  const pts = eq.map((v, i) => `${(i / (eq.length - 1)) * w},${h - ((v - min) / span) * (h - 12) - 6}`).join(" ");
  const yBase = h - ((100 - min) / span) * (h - 12) - 6;
  const up = eq[eq.length - 1] >= eq[0];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <line x1={0} y1={yBase} x2={w} y2={yBase} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
      <polyline points={pts} fill="none" stroke={up ? "#10b981" : "#f43f5e"} strokeWidth={2} />
    </svg>
  );
}
const selCls = "w-full rounded-lg border border-white/10 bg-ink-800 px-3 py-2 text-sm outline-none focus:border-tide-500/40";
export default function BacktestPage() {
  const [symbol, setSymbol] = useState("BTC");
  const [tf, setTf] = useState("1h");
  const [strat, setStrat] = useState(STRATS[0]);
  const [period, setPeriod] = useState(180);
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<Result | null>(null);
  const run = () => {
    setLoading(true);
    setTimeout(() => { setRes(runBacktest(`${symbol}-${tf}-${strat}-${period}`)); setLoading(false); }, 600);
  };
  return (
    <div className="space-y-5">
      <SectionTitle title="策略回測" desc="多商品 / 多時間框 / 多策略" />
      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-xs text-amber-200">
        以下為模擬資料，僅示範介面與資料流。真實策略表現請以 bot 的歷史結算（SIGNAL_RESULTS）為準。
      </div>
      <Card className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div><div className="mb-1 text-xs text-slate-500">商品</div>
          <select className={selCls} value={symbol} onChange={(e) => setSymbol(e.target.value)}>{SYMBOLS.map((s) => <option key={s}>{s}</option>)}</select></div>
        <div><div className="mb-1 text-xs text-slate-500">時間框架</div>
          <select className={selCls} value={tf} onChange={(e) => setTf(e.target.value)}>{TFS.map((s) => <option key={s}>{s}</option>)}</select></div>
        <div><div className="mb-1 text-xs text-slate-500">策略</div>
          <select className={selCls} value={strat} onChange={(e) => setStrat(e.target.value)}>{STRATS.map((s) => <option key={s}>{s}</option>)}</select></div>
        <div><div className="mb-1 text-xs text-slate-500">回測期間（天）</div>
          <select className={selCls} value={period} onChange={(e) => setPeriod(Number(e.target.value))}>{PERIODS.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
        <div className="flex items-end">
          <button onClick={run} disabled={loading}
            className="w-full rounded-lg bg-tide-500/15 py-2 text-sm font-semibold text-tide-300 hover:bg-tide-500/25 disabled:opacity-50">
            {loading ? "回測中…" : "執行回測"}
          </button>
        </div>
      </Card>
      {loading && <div className="h-56 animate-pulse rounded-xl bg-white/5" />}
      {res && !loading && (
        <div className="space-y-4">
          <Card className="p-4">
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-semibold">資金曲線（初始 100）</span>
              <span className={`font-mono ${res.totalRet >= 0 ? "text-up" : "text-down"}`}>{res.totalRet >= 0 ? "+" : ""}{res.totalRet}%</span>
            </div>
            <EquityChart eq={res.eq} />
          </Card>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="勝率" value={res.winRate + "%"} />
            <Stat label="交易次數" value={String(res.trades)} />
            <Stat label="最大回撤" value={"-" + res.maxDD + "%"} tone="down" />
            <Stat label="Profit Factor" value={String(res.pf)} tone={res.pf >= 1 ? "up" : "down"} />
            <Stat label="Sharpe" value={String(res.sharpe)} tone={res.sharpe >= 0 ? "up" : "down"} />
          </div>
        </div>
      )}
    </div>
  );
}
