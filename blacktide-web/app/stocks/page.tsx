"use client";
import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Minus, RefreshCw, BarChart2 } from "lucide-react";
import { Card } from "@/components/ui";
import { fmtPrice } from "@/lib/format";

const STOCKS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "AMD"];

interface StockData {
  ok: boolean; symbol: string; name: string; price: number; change24h: number;
  rsi: number; ma20: number; ma50: number; atrPct: number; momentum: number;
  trend: string; bias: string; confidence: number; risk: number;
  high52: number; low52: number; vol: number; volRatio: number;
  support: number[]; resistance: number[]; action: string;
}

const biasLabel = (b: string) => b === "long" ? "偏多看漲" : b === "short" ? "偏空看跌" : "中性整理";
const biasCls = (b: string) => b === "long" ? "text-up" : b === "short" ? "text-down" : "text-slate-300";
const BiasIcon = ({ b }: { b: string }) => b === "long" ? <TrendingUp size={15} className="text-up" /> : b === "short" ? <TrendingDown size={15} className="text-down" /> : <Minus size={15} className="text-slate-400" />;

function compactNum(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return String(n);
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
          <BarChart2 size={14} className="text-blue-400" />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-blue-400">美股 AI 分析</span>
        </div>
        <h1 className="font-display text-2xl font-bold">美股技術分析</h1>
        <p className="mt-1 text-sm text-slate-500">即時抓取 Yahoo Finance 數據，計算 RSI、均線、ATR、動能，AI 輸出操作建議</p>
      </div>

      {/* Symbol picker */}
      <div className="flex flex-wrap gap-2">
        {STOCKS.map((s) => (
          <button key={s} onClick={() => setSymbol(s)}
            className={`rounded-full px-3.5 py-1.5 font-mono text-xs font-bold transition-colors ${symbol === s ? "bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/40" : "bg-white/[0.04] text-slate-400 hover:bg-white/[0.08]"}`}>
            {s}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          <div className="h-28 animate-pulse rounded-xl bg-white/5" />
          <div className="h-44 animate-pulse rounded-xl bg-white/5" />
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="flex items-center gap-3 rounded-xl border border-down/20 bg-down/[0.06] px-4 py-3 text-sm text-down">
          {error}
          <button onClick={() => load(symbol)} className="ml-auto flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200"><RefreshCw size={12} /> 重試</button>
        </div>
      )}

      {/* Data */}
      {data && !loading && (
        <div className="space-y-4">
          {/* Price hero */}
          <Card className="p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-display text-lg font-bold">{data.symbol}</span>
                  <span className="text-sm text-slate-500">{data.name}</span>
                </div>
                <div className="mt-2 flex items-end gap-3">
                  <span className="font-mono text-3xl font-bold">${fmtPrice(data.price)}</span>
                  <span className={`pb-1 text-base font-semibold ${data.change24h >= 0 ? "text-up" : "text-down"}`}>
                    {data.change24h >= 0 ? "+" : ""}{data.change24h.toFixed(2)}%
                  </span>
                </div>
                <div className="mt-2 flex gap-4 text-xs text-slate-500">
                  <span>52W 高 <span className="text-slate-300 font-mono">${fmtPrice(data.high52)}</span></span>
                  <span>52W 低 <span className="text-slate-300 font-mono">${fmtPrice(data.low52)}</span></span>
                </div>
              </div>
              <div className="text-right">
                <div className="flex items-center justify-end gap-2">
                  <BiasIcon b={data.bias} />
                  <span className={`font-display text-xl font-bold ${biasCls(data.bias)}`}>{biasLabel(data.bias)}</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">信心 <span className="text-slate-300">{data.confidence}%</span> · 風險 <span className={data.risk >= 60 ? "text-down" : data.risk >= 40 ? "text-amber-400" : "text-up"}>{data.risk}</span></div>
              </div>
            </div>
          </Card>

          {/* Indicators grid */}
          <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-6">
            {cell("RSI(14)", String(data.rsi), data.rsi >= 70 ? "text-down" : data.rsi <= 30 ? "text-up" : "")}
            {cell("趨勢", data.trend === "up" ? "多頭排列" : data.trend === "down" ? "空頭排列" : "均線糾結", data.trend === "up" ? "text-up" : data.trend === "down" ? "text-down" : "")}
            {cell("ATR 波動", data.atrPct.toFixed(2) + "%", data.atrPct > 2.5 ? "text-amber-400" : "")}
            {cell("5日動能", (data.momentum >= 0 ? "+" : "") + data.momentum.toFixed(1) + "%", data.momentum >= 0 ? "text-up" : "text-down")}
            {cell("成交量", compactNum(data.vol), data.volRatio > 1.5 ? "text-amber-400" : "")}
            {cell("量/均量", data.volRatio.toFixed(2) + "×", data.volRatio > 2 ? "text-up" : "")}
          </div>

          {/* MA detail */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <Card className="p-3">
              <div className="mb-1 text-[10px] text-slate-500">均線狀態</div>
              <div className="space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-400">MA20</span>
                  <span className="font-mono">${data.ma20.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">MA50</span>
                  <span className="font-mono">${data.ma50.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">排列</span>
                  <span className={data.trend === "up" ? "text-up" : data.trend === "down" ? "text-down" : "text-slate-300"}>
                    {data.trend === "up" ? "多頭" : data.trend === "down" ? "空頭" : "糾結"}
                  </span>
                </div>
              </div>
            </Card>
            <div className="grid grid-rows-2 gap-1.5">
              <div className="rounded-lg bg-up/[0.06] px-3 py-2">
                <div className="text-[10px] text-slate-500">支撐參考</div>
                <div className="mt-0.5 font-mono text-xs font-bold text-up">{data.support.map((v) => "$" + fmtPrice(v)).join(" / ")}</div>
              </div>
              <div className="rounded-lg bg-down/[0.06] px-3 py-2">
                <div className="text-[10px] text-slate-500">壓力參考</div>
                <div className="mt-0.5 font-mono text-xs font-bold text-down">{data.resistance.map((v) => "$" + fmtPrice(v)).join(" / ")}</div>
              </div>
            </div>
          </div>

          {/* AI action */}
          <Card className="p-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">AI 操作建議</div>
            <div className="text-sm leading-relaxed text-slate-200">{data.action}</div>
            <div className="mt-3 border-t border-white/5 pt-3 text-[11px] text-slate-600">
              以上分析基於技術指標統計，不構成投資建議。美股受多重因素影響，請自行判斷風險。
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
