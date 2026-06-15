"use client";
import { useState } from "react";
import { SectionTitle, Card, Stat } from "@/components/ui";
import { makeRng } from "@/lib/format";
const SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "SUI", "PEPE", "NVDA", "TSLA", "AAPL", "META"];
const TFS = ["15m", "1h", "4h", "1d"];
const STRATS = ["黑潮綜合（7+1 投票）", "趨勢追隨", "動量策略", "BOS 突破", "均線排列", "支撐阻力", "訂單流", "新聞情緒"];
const PERIODS = [90, 180, 365, 730];
interface Result {
  eq: number[]; maxDD: number; totalRet: number; winRate: number; trades: number;
  pf: number; sharpe: number; sortino: number; avgWin: number; avgLoss: number;
  expectancy: number; payoff: number; maxConsecLoss: number;
}
function std(a: number[]) { if (a.length < 2) return 0; const m = a.reduce((x, y) => x + y, 0) / a.length; return Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / a.length); }
function runBacktest(seedStr: string): Result {
  let seed = 0; for (const c of seedStr) seed = (seed * 31 + c.charCodeAt(0)) | 0;
  const r = makeRng(seed);
  const trades = Math.round(45 + r() * 130);
  const pWin = 0.36 + r() * 0.26;
  const baseWin = 0.9 + r() * 1.6, baseLoss = -(0.6 + r() * 0.9);
  const eq: number[] = [100]; const rets: number[] = [];
  let wins = 0, losses = 0, sumWin = 0, sumLoss = 0, consec = 0, maxConsec = 0;
  for (let i = 0; i < trades; i++) {
    const win = r() < pWin;
    const pct = (win ? baseWin * (0.5 + r()) : baseLoss * (0.5 + r())) * 0.5;
    rets.push(pct);
    eq.push(Math.max(15, eq[eq.length - 1] * (1 + pct / 100)));
    if (win) { wins++; sumWin += pct; consec = 0; } else { losses++; sumLoss += pct; consec++; maxConsec = Math.max(maxConsec, consec); }
  }
  let peak = eq[0], maxDD = 0;
  for (const v of eq) { peak = Math.max(peak, v); maxDD = Math.max(maxDD, (peak - v) / peak); }
  const totalRet = eq[eq.length - 1] / 100 - 1;
  const realWin = trades ? wins / trades : 0;
  const avgWin = wins ? sumWin / wins : 0;
  const avgLoss = losses ? sumLoss / losses : 0;
  const expectancy = realWin * avgWin + (1 - realWin) * avgLoss;
  const pf = sumLoss < 0 ? sumWin / Math.abs(sumLoss) : (sumWin > 0 ? 9 : 0);
  const payoff = avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : 0;
  const m = rets.reduce((x, y) => x + y, 0) / (rets.length || 1);
  const sd = std(rets); const dd = std(rets.filter((x) => x < 0));
  return {
    eq, maxDD: +(maxDD * 100).toFixed(1), totalRet: +(totalRet * 100).toFixed(1),
    winRate: Math.round(realWin * 100), trades,
    pf: +pf.toFixed(2), sharpe: +(sd ? m / sd : 0).toFixed(2), sortino: +(dd ? m / dd : 0).toFixed(2),
    avgWin: +avgWin.toFixed(2), avgLoss: +avgLoss.toFixed(2), expectancy: +expectancy.toFixed(2),
    payoff: +payoff.toFixed(2), maxConsecLoss: maxConsec,
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
      <SectionTitle title="策略回測" desc="12 商品 × 4 時間框 × 8 策略 · 完整風險指標" />
      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-xs text-amber-200">
        以下為模擬資料，僅示範介面與指標。真實策略表現請以 bot 的歷史結算（SIGNAL_RESULTS）為準——這正是「先驗證再加功能」的核心。
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
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <Stat label="總報酬" value={(res.totalRet >= 0 ? "+" : "") + res.totalRet + "%"} tone={res.totalRet >= 0 ? "up" : "down"} />
            <Stat label="勝率" value={res.winRate + "%"} />
            <Stat label="交易次數" value={String(res.trades)} />
            <Stat label="最大回撤" value={"-" + res.maxDD + "%"} tone="down" />
            <Stat label="期望值/筆" value={(res.expectancy >= 0 ? "+" : "") + res.expectancy + "%"} tone={res.expectancy >= 0 ? "up" : "down"} />
            <Stat label="Profit Factor" value={String(res.pf)} tone={res.pf >= 1 ? "up" : "down"} />
            <Stat label="平均盈" value={"+" + res.avgWin + "%"} tone="up" />
            <Stat label="平均虧" value={res.avgLoss + "%"} tone="down" />
            <Stat label="賺賠比" value={String(res.payoff)} sub="平均盈 ÷ 平均虧" />
            <Stat label="最大連虧" value={res.maxConsecLoss + " 筆"} />
            <Stat label="Sharpe" value={String(res.sharpe)} tone={res.sharpe >= 0 ? "up" : "down"} />
            <Stat label="Sortino" value={String(res.sortino)} tone={res.sortino >= 0 ? "up" : "down"} />
          </div>
          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-3 text-[11px] leading-relaxed text-slate-400">
            判讀重點：看「期望值/筆」是否穩定為正（且 ≥ 成本約 0.15–0.2%），而非只看勝率。高勝率配差賺賠比可能仍是負期望。
          </div>
        </div>
      )}
    </div>
  );
}
