"use client";
import { useState } from "react";
import { Card, Stat, Skeleton } from "@/components/ui";
import { makeRng } from "@/lib/format";
import { Play, TrendingUp, FlaskConical, AlertTriangle } from "lucide-react";
import { C } from "@/lib/theme";
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
  const w = 560, h = 180;
  const min = Math.min(...eq), max = Math.max(...eq), span = max - min || 1;
  const pts = eq.map((v, i) => `${(i / (eq.length - 1)) * w},${h - ((v - min) / span) * (h - 12) - 6}`).join(" ");
  const yBase = h - ((100 - min) / span) * (h - 12) - 6;
  const up = eq[eq.length - 1] >= eq[0];
  const color = up ? "#10b981" : "#f43f5e";
  const fillPts = `${pts} ${w},${h} 0,${h}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <defs>
        <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <line x1={0} y1={yBase} x2={w} y2={yBase} stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />
      <polygon points={fillPts} fill="url(#eqFill)" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth={2.5} />
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
      {/* Hero */}
      <section className="relative overflow-hidden rounded-2xl p-5 sm:p-6" style={{ border: `1px solid ${C.linePrimary}`, background: "linear-gradient(135deg, rgba(0,212,255,0.07), rgba(10,12,18,0.4))" }}>
        
        <div className="relative">
          <div className="mb-2 flex items-center gap-2">
            <TrendingUp size={15} color={C.teal} />
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2, color: C.teal }}>STRATEGY VALIDATION · 示意模擬</span>
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.01em", color: C.ink }}>策略驗證工具 · 示意模擬</h1>
          <p className="mt-2 max-w-lg" style={{ fontSize: 13, lineHeight: 1.7, color: C.mut }}>
            這裡的勝率、期望值、最大回撤與 Sharpe 比率是<b style={{ color: C.primary }}>示意模擬數據</b>，用來示範介面與指標算法，
            <b style={{ color: C.primary }}>不是黑潮船長的真實歷史績效</b>。真實策略表現以 bot 歷史結算（SIGNAL_RESULTS）為準。
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {["8 大策略", "12 標的", "4 時間框架", "12 項風險指標"].map((t) => (
              <span key={t} className="rounded-full px-3 py-1" style={{ fontSize: 11, border: `1px solid ${C.teal}33`, background: "rgba(0,212,255,0.06)", color: C.teal }}>{t}</span>
            ))}
          </div>
        </div>
      </section>

      {/* Config */}
      <Card className="relative overflow-hidden p-4">
        
        <div className="mb-3 flex items-center gap-1.5" style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.5, color: C.dim, textTransform: "uppercase" }}>回測設定</div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div><div className="mb-1 text-xs text-slate-500">標的</div>
            <select className={selCls} value={symbol} onChange={(e) => setSymbol(e.target.value)}>{SYMBOLS.map((s) => <option key={s}>{s}</option>)}</select></div>
          <div><div className="mb-1 text-xs text-slate-500">時間框架</div>
            <select className={selCls} value={tf} onChange={(e) => setTf(e.target.value)}>{TFS.map((s) => <option key={s}>{s}</option>)}</select></div>
          <div><div className="mb-1 text-xs text-slate-500">策略</div>
            <select className={selCls} value={strat} onChange={(e) => setStrat(e.target.value)}>{STRATS.map((s) => <option key={s}>{s}</option>)}</select></div>
          <div><div className="mb-1 text-xs text-slate-500">回測期間（天）</div>
            <select className={selCls} value={period} onChange={(e) => setPeriod(Number(e.target.value))}>{PERIODS.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
          <div className="flex items-end">
            <button onClick={run} disabled={loading}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-tide-500/15 py-2.5 text-sm font-semibold text-tide-300 hover:bg-tide-500/25 disabled:opacity-50">
              <Play size={12} fill="currentColor" />{loading ? "計算中…" : "執行回測"}
            </button>
          </div>
        </div>
        <div className="mt-3 text-[10px] text-slate-600">以下為模擬資料，示範指標與介面；真實策略表現以 bot 歷史結算（SIGNAL_RESULTS）為準。</div>
      </Card>

      {/* Empty state */}
      {!res && !loading && (
        <div className="flex flex-col items-center py-16 text-center">
          <FlaskConical size={36} className="mb-3 text-slate-700" />
          <div className="text-sm text-slate-500">選擇設定後點「執行回測」查看完整績效報告</div>
          <div className="mt-1 text-[11px] text-slate-600">勝率 · 期望值 · Sharpe · 資金曲線 · 12 項指標</div>
        </div>
      )}
      {loading && (
        <Card className="p-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
          <Skeleton className="mt-4 h-32 w-full" />
        </Card>
      )}

      {/* Results */}
      {res && !loading && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 rounded-xl px-4 py-2.5" style={{ border: `1px solid ${C.primary}40`, background: "rgba(0,212,255,0.08)" }}>
            <AlertTriangle size={14} color={C.primary} className="shrink-0" />
            <span style={{ fontSize: 12, color: C.primary }}>以下為示意模擬結果，非黑潮船長真實歷史績效</span>
          </div>
          {/* Summary 4-big-number row */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card className="p-4 text-center">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">總報酬</div>
              <div className={`mt-1 font-mono text-3xl font-bold ${res.totalRet >= 0 ? "text-up" : "text-down"}`}>
                {res.totalRet >= 0 ? "+" : ""}{res.totalRet}%
              </div>
              <div className="mt-0.5 text-[10px] text-slate-600">{period} 天 · {res.trades} 筆</div>
            </Card>
            <Card className="p-4 text-center">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">勝率</div>
              <div className={`mt-1 font-mono text-3xl font-bold ${res.winRate >= 50 ? "text-up" : "text-slate-300"}`}>{res.winRate}%</div>
              <div className="mt-0.5 text-[10px] text-slate-600">賺賠比 {res.payoff}×</div>
            </Card>
            <Card className="p-4 text-center">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">Profit Factor</div>
              <div className={`mt-1 font-mono text-3xl font-bold ${res.pf >= 1.5 ? "text-up" : res.pf >= 1 ? "text-amber-400" : "text-down"}`}>{res.pf}</div>
              <div className="mt-0.5 text-[10px] text-slate-600">≥ 1.5 為理想</div>
            </Card>
            <Card className="p-4 text-center">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">最大回撤</div>
              <div className="mt-1 font-mono text-3xl font-bold text-down">-{res.maxDD}%</div>
              <div className="mt-0.5 text-[10px] text-slate-600">最長連虧 {res.maxConsecLoss} 筆</div>
            </Card>
          </div>

          {/* Equity Curve */}
          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold">資金曲線（初始 = 100）</span>
              <span className={`font-mono text-sm ${res.totalRet >= 0 ? "text-up" : "text-down"}`}>
                100 → {res.eq[res.eq.length - 1].toFixed(1)}
              </span>
            </div>
            <EquityChart eq={res.eq} />
          </Card>

          {/* Grouped stats 3-col */}
          <div className="grid gap-3 sm:grid-cols-3">
            <Card className="p-3">
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">核心績效</div>
              <div className="space-y-2">
                <Stat label="期望值/筆" value={(res.expectancy >= 0 ? "+" : "") + res.expectancy + "%"} tone={res.expectancy >= 0 ? "up" : "down"} />
                <Stat label="賺賠比" value={res.payoff + "×"} sub="平均盈 ÷ 平均虧" />
                <Stat label="平均盈利" value={"+" + res.avgWin + "%"} tone="up" />
                <Stat label="平均虧損" value={res.avgLoss + "%"} tone="down" />
              </div>
            </Card>
            <Card className="p-3">
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">風險指標</div>
              <div className="space-y-2">
                <Stat label="Sharpe 比率" value={String(res.sharpe)} tone={res.sharpe >= 0 ? "up" : "down"} sub="≥ 1.0 良好" />
                <Stat label="Sortino 比率" value={String(res.sortino)} tone={res.sortino >= 0 ? "up" : "down"} />
                <Stat label="最大回撤" value={"-" + res.maxDD + "%"} tone="down" />
                <Stat label="最大連虧筆數" value={res.maxConsecLoss + " 筆"} />
              </div>
            </Card>
            <Card className="p-3">
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">判讀指引</div>
              <div className="space-y-1.5 text-[11px] leading-relaxed text-slate-500">
                <p>· <b className="text-slate-300">期望值 &gt; 0.2%</b>：每筆平均貢獻為正，策略可持續</p>
                <p>· <b className="text-slate-300">PF &gt; 1.5</b>：總盈利是總虧損 1.5 倍以上</p>
                <p>· 勝率 &lt; 50% 不代表策略失敗，關鍵看賺賠比</p>
                <p>· Sortino 高 = 虧損端控制好，比 Sharpe 更務實</p>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
