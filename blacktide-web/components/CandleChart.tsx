"use client";
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";
const TFS = [{ label: "15m", v: "15" }, { label: "1h", v: "60" }, { label: "4h", v: "240" }, { label: "1D", v: "D" }];
interface Candle { time: UTCTimestamp; open: number; high: number; low: number; close: number; }
export default function CandleChart({ bybitSymbol, livePrice }: { bybitSymbol: string; livePrice?: number }) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const vols = useRef<ISeriesApi<"Histogram"> | null>(null);
  const lastBar = useRef<Candle | null>(null);
  const [tf, setTf] = useState("60");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!box.current) return;
    const c = createChart(box.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.04)" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
      timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: true, secondsVisible: false },
    });
    candles.current = c.addCandlestickSeries({
      upColor: "#10b981", downColor: "#f43f5e",
      borderUpColor: "#10b981", borderDownColor: "#f43f5e",
      wickUpColor: "#10b981", wickDownColor: "#f43f5e",
    });
    vols.current = c.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol" });
    c.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    chart.current = c;
    return () => { c.remove(); chart.current = null; candles.current = null; vols.current = null; };
  }, []);
  useEffect(() => {
    let dead = false;
    setLoading(true);
    fetch(`/api/klines?symbol=${bybitSymbol}&interval=${tf}`)
      .then((r) => r.json())
      .then((d) => {
        if (dead || !candles.current || !vols.current) return;
        const bars: { time: UTCTimestamp; open: number; high: number; low: number; close: number; volume: number }[] = d.bars || [];
        candles.current.setData(bars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));
        vols.current.setData(bars.map((b) => ({
          time: b.time, value: b.volume,
          color: b.close >= b.open ? "rgba(16,185,129,0.35)" : "rgba(244,63,94,0.35)",
        })));
        const last = bars[bars.length - 1];
        lastBar.current = last ? { time: last.time, open: last.open, high: last.high, low: last.low, close: last.close } : null;
        chart.current?.timeScale().fitContent();
      })
      .catch(() => {})
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [bybitSymbol, tf]);
  useEffect(() => {
    if (!livePrice || !lastBar.current || !candles.current) return;
    const b = lastBar.current;
    const nb: Candle = { ...b, close: livePrice, high: Math.max(b.high, livePrice), low: Math.min(b.low, livePrice) };
    lastBar.current = nb;
    candles.current.update(nb);
  }, [livePrice]);
  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5 px-1">
        {TFS.map((t) => (
          <button key={t.v} onClick={() => setTf(t.v)}
            className={`rounded-md px-2.5 py-1 text-[11px] transition-colors ${tf === t.v ? "bg-tide-500/20 text-tide-300" : "text-slate-500 hover:text-slate-300"}`}>
            {t.label}
          </button>
        ))}
        {loading && <span className="ml-auto text-[11px] text-slate-600">載入中…</span>}
      </div>
      <div ref={box} className="h-[300px] w-full md:h-[420px]" />
    </div>
  );
}
