"use client";

import { Ticker } from "@/lib/types";
import { fmtPrice, fmtPct } from "@/lib/format";

export default function TickerTape({ tickers }: { tickers: Ticker[] }) {
  if (!tickers.length) return null;
  const items = [...tickers, ...tickers]; // 複製一份做無縫循環
  return (
    <div className="relative -mx-4 overflow-hidden border-y border-tide-500/15 bg-ink-900/70 py-2 lg:mx-0 lg:rounded-xl lg:border lg:border-white/[0.07]">
      <div className="animate-marquee flex w-max items-center gap-6 px-4">
        {items.map((t, i) => (
          <span key={t.symbol + "-" + i} className="flex shrink-0 items-center gap-1.5 font-mono text-xs">
            <span className="font-semibold text-slate-300">{t.symbol}</span>
            <span className="text-slate-400">${fmtPrice(t.price)}</span>
            <span className={t.changePct >= 0 ? "text-up" : "text-down"}>{fmtPct(t.changePct)}</span>
          </span>
        ))}
      </div>
      <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-ink-950 to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-ink-950 to-transparent" />
    </div>
  );
}
