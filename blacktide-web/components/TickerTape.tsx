"use client";
import { Ticker } from "@/lib/types";
import { fmtPrice, fmtPct } from "@/lib/format";
import { Marquee } from "@/components/ui/marquee";

/* 行情跑馬燈：容器改用 Magic UI Marquee（無縫循環 + hover 暫停），
 * ticker 資料與 WS 即時價更新邏輯完全不變（items 由上層 useMarket 傳入）。 */
export default function TickerTape({ tickers }: { tickers: Ticker[] }) {
  if (!tickers.length) return null;
  return (
    <div className="relative -mx-3 overflow-hidden border-y border-tide-500/15 bg-ink-900/70 md:mx-0 md:rounded-xl md:border md:border-white/[0.07]">
      <Marquee pauseOnHover className="px-0 py-2 [--duration:45s] [--gap:1.5rem]">
        {tickers.map((t) => (
          <span key={t.symbol} className="flex shrink-0 items-center gap-1.5 font-mono text-xs">
            <span className="font-semibold text-slate-300">{t.symbol}</span>
            <span className="text-slate-400">${fmtPrice(t.price)}</span>
            <span className={t.changePct >= 0 ? "text-up" : "text-down"}>{fmtPct(t.changePct)}</span>
          </span>
        ))}
      </Marquee>
      <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-ink-950 to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-ink-950 to-transparent" />
    </div>
  );
}
