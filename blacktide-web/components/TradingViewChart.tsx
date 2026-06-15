"use client";
import { useEffect, useRef } from "react";
export default function TradingViewChart({ tvSymbol, height = 380 }: { tvSymbol: string; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.innerHTML = '<div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>';
    const s = document.createElement("script");
    s.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    s.async = true;
    s.innerHTML = JSON.stringify({
      autosize: true, symbol: tvSymbol, interval: "60", timezone: "Asia/Taipei",
      theme: "dark", style: "1", locale: "zh_TW", allow_symbol_change: false,
      hide_side_toolbar: true, backgroundColor: "rgba(10,12,18,1)", gridColor: "rgba(255,255,255,0.04)",
    });
    el.appendChild(s);
    return () => { el.innerHTML = ""; };
  }, [tvSymbol]);
  return (
    <div style={{ height }} className="w-full overflow-hidden rounded-lg border border-white/5">
      <div ref={ref} className="tradingview-widget-container h-full w-full" />
    </div>
  );
}
