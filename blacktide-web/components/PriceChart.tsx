"use client";

import { useEffect, useRef, useState } from "react";
import { Candle } from "@/lib/types";

const INTERVALS: { label: string; v: string }[] = [
  { label: "15m", v: "15" }, { label: "1h", v: "60" }, { label: "4h", v: "240" }, { label: "1D", v: "D" },
];

// lightweight-charts 自繪 K 線。動態 import 避免 SSR 觸碰 window；資料走 /api/klines（Bybit）。
export default function PriceChart({ symbol }: { symbol: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [interval, setInterval2] = useState("60");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    let chart: { remove: () => void; applyOptions: (o: unknown) => void } | null = null;
    let ro: ResizeObserver | null = null;

    (async () => {
      const el = box.current;
      if (!el) return;
      try {
        const r = await fetch(`/api/klines?symbol=${symbol}&interval=${interval}`, { cache: "no-store" });
        const j = await r.json();
        const candles: Candle[] = j?.candles ?? [];
        if (disposed || !candles.length) { if (!candles.length) setErr("無 K 線資料"); return; }
        setErr(null);

        const { createChart, ColorType } = await import("lightweight-charts");
        if (disposed) return;
        el.innerHTML = "";
        const c = createChart(el, {
          layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#94a3b8" },
          grid: { vertLines: { color: "#131c2b" }, horzLines: { color: "#131c2b" } },
          rightPriceScale: { borderColor: "#1a2436" },
          timeScale: { borderColor: "#1a2436", timeVisible: true },
          width: el.clientWidth, height: 360,
          autoSize: false,
        });
        chart = c as unknown as { remove: () => void; applyOptions: (o: unknown) => void };
        const series = c.addCandlestickSeries({
          upColor: "#10b981", downColor: "#f43f5e", borderVisible: false,
          wickUpColor: "#10b981", wickDownColor: "#f43f5e",
        });
        // lightweight-charts 需要 time 遞增；資料已轉舊→新
        series.setData(candles as unknown as Parameters<typeof series.setData>[0]);
        c.timeScale().fitContent();

        ro = new ResizeObserver(() => { if (el) c.applyOptions({ width: el.clientWidth }); });
        ro.observe(el);
      } catch (e) {
        if (!disposed) setErr(String(e));
      }
    })();

    return () => {
      disposed = true;
      if (ro) ro.disconnect();
      if (chart) { try { chart.remove(); } catch { /* noop */ } }
    };
  }, [symbol, interval]);

  return (
    <div className="card p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-200">{symbol} · 永續 K 線</div>
        <div className="flex gap-1">
          {INTERVALS.map((it) => (
            <button
              key={it.v}
              onClick={() => setInterval2(it.v)}
              className={
                "rounded px-2 py-0.5 text-[11px] " +
                (interval === it.v ? "bg-tide-500/20 text-tide-300" : "text-slate-500 hover:text-slate-300")
              }
            >
              {it.label}
            </button>
          ))}
        </div>
      </div>
      <div ref={box} className="w-full" style={{ height: 360 }} />
      {err && <div className="mt-2 text-xs text-down">K 線讀取失敗：{err}</div>}
    </div>
  );
}
