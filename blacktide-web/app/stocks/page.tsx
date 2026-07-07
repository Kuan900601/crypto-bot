"use client";
import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Minus, RefreshCw, BarChart2, Activity } from "lucide-react";
import { Card, Skeleton } from "@/components/ui";
import { fmtPrice } from "@/lib/format";
import { C, MONO, SERIF } from "@/lib/theme";
import Corner from "@/components/site/Corner";
const STOCKS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "AMD"];

interface StockData {
  ok: boolean; symbol: string; name: string; sector: string; peers: string[];
  price: number; change24h: number;
  rsi: number; ma20: number; ma50: number; ma200: number;
  trend: string; trendDetail: string; atrPct: number;
  momentum5: number; momentum20: number;
  bias: string; confidence: number; risk: number;
  high52: number; low52: number; range52Pct: number;
  vol: number; avgVol: number; volRatio: number;
  boll: { upper: number; mid: number; lower: number }; bollPct: number;
  macd: { macd: number; signal: number; hist: number };
  support: number[]; resistance: number[];
  action: string; basis: string[];
}

const biasLabel = (b: string) => b === "long" ? "偏多看漲" : b === "short" ? "偏空看跌" : "中性整理";
const biasCls = (b: string) => b === "long" ? "text-up" : b === "short" ? "text-down" : "text-slate-300";
const BiasIcon = ({ b }: { b: string }) => b === "long" ? <TrendingUp size={16} className="text-up" /> : b === "short" ? <TrendingDown size={16} className="text-down" /> : <Minus size={16} className="text-slate-400" />;

function compactNum(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return String(n);
}

function ProgressBar({ pct, colorCls = "bg-tide-500" }: { pct: number; colorCls?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.08]">
      <div className={`h-full rounded-full ${colorCls}`} style={{ width: Math.max(2, Math.min(100, pct)) + "%" }} />
    </div>
  );
}

export default function StocksPage() {
  const [symbol, setSymbol] = useState("NVDA");
  const [data, setData] = useState<StockData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = (sym: string) => {
    setLoading(true); setError(""); setData(null);
    fetch("/api/stocks?symbol=" + sym)
      .then((r) => r.json())
      .then((d) => { if (d.ok) setData(d); else setError("資料暫時無法取得，請稍後再試"); })
      .catch(() => setError("連線失敗，請稍後再試"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(symbol); }, [symbol]);

  const cell = (label: string, val: string, cls = "") => (
    <div className="rounded-lg bg-white/[0.03] p-2.5 text-center">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={"mt-0.5 font-mono text-xs font-semibold " + cls}>{val}</div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="mb-1 flex items-center gap-2">
          <BarChart2 size={14} color={C.teal} />
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2, color: C.teal }}>美股 AI 分析</span>
        </div>
        <h1 className="accent-text" style={{ fontFamily: SERIF, fontSize: 24, fontWeight: 700 }}>美股技術分析</h1>
        <p className="mt-1" style={{ fontSize: 13, color: C.mut }}>基於 Yahoo Finance 90 日數據 · RSI · 布林通道 · MACD · 均線 · 量能分析</p>
      </div>

      {/* Symbol picker */}
      <div className="flex flex-wrap gap-2">
        {STOCKS.map((s) => (
          <button key={s} onClick={() => setSymbol(s)} className="rounded-full px-3.5 py-1.5" style={{
            fontFamily: MONO, fontSize: 12, fontWeight: 700,
            border: `1px solid ${symbol === s ? C.teal + "70" : C.line}`,
            background: symbol === s ? "rgba(0,212,255,0.12)" : "transparent",
            color: symbol === s ? C.teal : C.mut,
          }}>
            {s}
          </button>
        ))}
      </div>

      {loading && (
        <div className="space-y-3">
          <Card className="p-5"><Skeleton className="h-6 w-28" /><Skeleton className="mt-3 h-4 w-20" /></Card>
          <Card className="p-4"><Skeleton className="h-40 w-full" /></Card>
        </div>
      )}
      {error && !loading && (
        <div className="flex items-center gap-3 rounded-xl border border-down/20 bg-down/[0.06] px-4 py-3 text-sm text-down">
          {error} <button onClick={() => load(symbol)} className="ml-auto flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200"><RefreshCw size={12} /> 重試</button>
        </div>
      )}

      {data && !loading && (
        <div className="space-y-4">
          {/* Price + bias hero */}
          <Card className="relative overflow-hidden p-5">
            <Corner pos="tl" /><Corner pos="br" />
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-display text-xl font-bold">{data.symbol}</span>
                  <span className="text-sm text-slate-400">{data.name}</span>
                  <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] text-blue-300">{data.sector}</span>
                </div>
                <div className="mt-2 flex items-end gap-3">
                  <span className="font-mono text-3xl font-bold">${fmtPrice(data.price)}</span>
                  <span className={`pb-1 text-base font-semibold ${data.change24h >= 0 ? "text-up" : "text-down"}`}>
                    {data.change24h >= 0 ? "+" : ""}{data.change24h.toFixed(2)}%
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                  <span>52W 高 <span className="font-mono text-slate-300">${fmtPrice(data.high52)}</span></span>
                  <span>52W 低 <span className="font-mono text-slate-300">${fmtPrice(data.low52)}</span></span>
                </div>
                {/* 52-week range bar */}
                <div className="mt-2 w-48">
                  <div className="mb-1 flex justify-between text-[10px] text-slate-600">
                    <span>低</span><span>位置 {data.range52Pct}%</span><span>高</span>
                  </div>
                  <ProgressBar pct={data.range52Pct} colorCls={data.range52Pct > 70 ? "bg-up" : data.range52Pct < 30 ? "bg-down" : "bg-tide-500"} />
                </div>
              </div>
              <div className="text-right">
                <div className="flex items-center justify-end gap-2">
                  <BiasIcon b={data.bias} />
                  <span className={`font-display text-2xl font-bold ${biasCls(data.bias)}`}>{biasLabel(data.bias)}</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">信心 <span className="text-slate-300">{data.confidence}%</span></div>
                <div className="mt-0.5 text-xs text-slate-500">風險 <span className={data.risk >= 60 ? "text-down" : data.risk >= 40 ? "text-amber-400" : "text-up"}>{data.risk}</span></div>
                {data.peers.length > 0 && (
                  <div className="mt-2 text-[11px] text-slate-600">同業：{data.peers.join(" / ")}</div>
                )}
              </div>
            </div>
          </Card>

          {/* Main indicators grid */}
          <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-6">
            {cell("RSI(14)", String(data.rsi), data.rsi >= 70 ? "text-down" : data.rsi <= 30 ? "text-up" : "")}
            {cell("趨勢", data.trend === "up" ? "多頭" : data.trend === "down" ? "空頭" : "糾結", data.trend === "up" ? "text-up" : data.trend === "down" ? "text-down" : "")}
            {cell("ATR 波動", data.atrPct.toFixed(2) + "%", data.atrPct > 2.5 ? "text-amber-400" : "")}
            {cell("5日動能", (data.momentum5 >= 0 ? "+" : "") + data.momentum5.toFixed(1) + "%", data.momentum5 >= 0 ? "text-up" : "text-down")}
            {cell("20日動能", (data.momentum20 >= 0 ? "+" : "") + data.momentum20.toFixed(1) + "%", data.momentum20 >= 0 ? "text-up" : "text-down")}
            {cell("量/均量", data.volRatio.toFixed(2) + "×", data.volRatio > 1.5 ? "text-amber-400" : "")}
          </div>

          {/* Detailed analysis cards */}
          <div className="grid gap-3 sm:grid-cols-3">
            {/* Moving averages */}
            <Card className="p-4">
              <div className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">均線分析</div>
              <div className="space-y-2 text-xs">
                {[["MA20", data.ma20], ["MA50", data.ma50], ["MA200", data.ma200]].map(([label, val]) => (
                  <div key={label} className="flex justify-between items-center">
                    <span className="text-slate-400">{label}</span>
                    <div className="text-right">
                      <span className="font-mono text-slate-200">${fmtPrice(val as number)}</span>
                      <span className={`ml-2 text-[10px] ${data.price > (val as number) ? "text-up" : "text-down"}`}>
                        {data.price > (val as number) ? "▲" : "▼"}
                      </span>
                    </div>
                  </div>
                ))}
                <div className="border-t border-white/5 pt-2 text-[11px] text-slate-500">
                  {data.trendDetail === "up" ? "三均線多頭排列，強勢" :
                   data.trendDetail === "up_weak" ? "MA20>MA50，轉多初期" :
                   data.trendDetail === "down" ? "三均線空頭排列，弱勢" :
                   data.trendDetail === "down_weak" ? "MA20<MA50，轉弱" : "均線糾結中"}
                </div>
              </div>
            </Card>

            {/* Bollinger + MACD */}
            <Card className="p-4">
              <div className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">布林通道 · MACD</div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-slate-400">布林上軌</span><span className="font-mono text-down">${fmtPrice(data.boll.upper)}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">中軌 (MA20)</span><span className="font-mono text-slate-300">${fmtPrice(data.boll.mid)}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">布林下軌</span><span className="font-mono text-up">${fmtPrice(data.boll.lower)}</span></div>
                <div className="mt-1.5">
                  <div className="mb-1 text-[10px] text-slate-500">通道位置 {data.bollPct}%</div>
                  <ProgressBar pct={data.bollPct} colorCls={data.bollPct > 80 ? "bg-down" : data.bollPct < 20 ? "bg-up" : "bg-tide-500"} />
                </div>
                <div className="border-t border-white/5 pt-2">
                  <div className="flex justify-between"><span className="text-slate-400">MACD 柱</span>
                    <span className={`font-mono ${data.macd.hist >= 0 ? "text-up" : "text-down"}`}>{data.macd.hist >= 0 ? "+" : ""}{data.macd.hist}</span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Volume */}
            <Card className="p-4">
              <div className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">量能分析</div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-slate-400">今日成交量</span><span className="font-mono">{compactNum(data.vol)}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">20 日均量</span><span className="font-mono text-slate-400">{compactNum(data.avgVol)}</span></div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">量/均量</span>
                  <span className={`font-mono font-bold ${data.volRatio > 1.5 ? "text-amber-400" : data.volRatio < 0.7 ? "text-slate-600" : "text-slate-200"}`}>
                    {data.volRatio.toFixed(2)}×
                  </span>
                </div>
                <div className="mt-1">
                  <ProgressBar pct={Math.min(100, data.volRatio * 50)} colorCls={data.volRatio > 1.5 ? "bg-amber-400" : "bg-blue-500"} />
                </div>
                <div className="border-t border-white/5 pt-2 text-[11px] text-slate-500">
                  {data.volRatio > 1.5 ? "放量，市場關注度高" : data.volRatio < 0.7 ? "縮量，市場觀望" : "成交量正常"}
                </div>
              </div>
            </Card>
          </div>

          {/* Support / Resistance */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-xl bg-up/[0.06] border border-up/10 px-4 py-3">
              <div className="mb-1 text-[10px] text-slate-500">技術支撐</div>
              <div className="space-y-1">
                {data.support.map((v, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-slate-500">S{i + 1}</span>
                    <span className="font-mono font-bold text-up">${fmtPrice(v)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl bg-down/[0.06] border border-down/10 px-4 py-3">
              <div className="mb-1 text-[10px] text-slate-500">技術壓力</div>
              <div className="space-y-1">
                {data.resistance.map((v, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-slate-500">R{i + 1}</span>
                    <span className="font-mono font-bold text-down">${fmtPrice(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* AI comprehensive action */}
          <Card className="p-4">
            <div className="mb-2 flex items-center gap-2">
              <Activity size={13} className="text-blue-400" />
              <span className="text-sm font-semibold">綜合技術分析</span>
            </div>
            <div className="text-sm leading-relaxed text-slate-200">{data.action}</div>
            {data.basis.length > 0 && (
              <div className="mt-3 space-y-1.5 border-t border-white/5 pt-3">
                {data.basis.map((b, i) => <div key={i} className="text-[11px] leading-relaxed text-slate-500">· {b}</div>)}
              </div>
            )}
            <div className="mt-3 text-[11px] text-slate-600">以上分析基於技術指標統計，不構成投資建議。股市受多重因素影響，請自行評估風險。</div>
          </Card>
        </div>
      )}
    </div>
  );
}
