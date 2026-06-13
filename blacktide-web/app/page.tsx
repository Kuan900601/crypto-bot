"use client";

import { useFetch } from "@/lib/useFetch";
import { useMarket } from "@/lib/useMarket";
import { SignalsResponse } from "@/lib/types";
import { fmtPrice, fmtPct, compactZh } from "@/lib/format";
import StatCard from "@/components/StatCard";
import SignalCard from "@/components/SignalCard";
import Sparkline from "@/components/Sparkline";
import PageHeader from "@/components/PageHeader";
import TickerTape from "@/components/TickerTape";
import { SourceBadge } from "@/components/Badges";
import Link from "next/link";

export default function Home() {
  const sig = useFetch<SignalsResponse>("/api/signals", 15000);
  const { tickers, stats: mktStats, src: mktSrc } = useMarket();

  const stats = sig.data?.stats;
  const active = sig.data?.active ?? [];

  return (
    <div>
      <div className="mb-5"><TickerTape tickers={tickers} /></div>
      <PageHeader
        title="總覽 Overview"
        subtitle="策略驗證期 · 所有數據為 SIM 模擬，期望值未達標前不代表可實盤"
        right={sig.data && <SourceBadge source={sig.data.source} error={sig.data.error} />}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="毛期望值 / 筆"
          value={stats ? fmtPct(stats.ev) : "—"}
          sub={stats ? `樣本 ${stats.n} 筆` : "讀取中"}
          tone={stats ? (stats.ev > 0 ? "up" : "down") : "neutral"}
        />
        <StatCard
          label="勝率"
          value={stats ? stats.winRate.toFixed(1) + "%" : "—"}
          sub={stats ? `Wilson 下界 ${stats.wilsonLb.toFixed(1)}%` : ""}
        />
        <StatCard
          label="平均盈 / 平均虧"
          value={stats ? `${stats.avgWin.toFixed(1)} / ${stats.avgLoss.toFixed(1)}` : "—"}
          sub="目標 盈 ≥ 2× 虧"
          tone={stats ? (stats.avgWin > Math.abs(stats.avgLoss) ? "up" : "down") : "neutral"}
        />
        <StatCard
          label="最大連續虧損"
          value={stats ? stats.maxLossStreak : "—"}
          sub="連敗為正期望策略的必然"
          tone={stats && stats.maxLossStreak >= 5 ? "down" : "neutral"}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* 追蹤中信號 */}
        <section className="xl:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-300">追蹤中信號（{active.length}）</h2>
            <Link href="/signals" className="text-xs text-tide-400 hover:text-tide-300">全部 →</Link>
          </div>
          {active.length === 0 ? (
            <div className="card p-8 text-center text-sm text-slate-500">目前沒有追蹤中的信號</div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {active.slice(0, 6).map((s) => (
                <SignalCard key={s.id} s={s} />
              ))}
            </div>
          )}
        </section>

        {/* 行情 */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-300">行情</h2>
            <span className="text-[11px] text-slate-600">
              {mktSrc.crypto === "bybit" ? "Bybit 即時" : "Mock"}
            </span>
          </div>
          <div className="card divide-y divide-ink-700">
            {tickers.slice(0, 8).map((t) => {
              const up = t.changePct >= 0;
              return (
                <div key={t.symbol} className="flex items-center gap-3 px-3 py-2.5">
                  <div className="w-14">
                    <div className="text-sm font-semibold text-slate-100">{t.symbol}</div>
                    <div className="text-[10px] text-slate-500">{t.class === "stock" ? "股票" : "加密"}</div>
                  </div>
                  <Sparkline data={t.spark} up={up} width={72} height={24} />
                  <div className="ml-auto text-right">
                    <div className="font-mono text-sm text-slate-200">{fmtPrice(t.price)}</div>
                    <div className={"font-mono text-xs " + (up ? "text-up" : "text-down")}>{fmtPct(t.changePct)}</div>
                  </div>
                </div>
              );
            })}
          </div>
          {mktStats && (
            <div className="card mt-3 grid grid-cols-3 gap-2 p-3 text-center">
              <div>
                <div className="text-[10px] text-slate-500">恐懼貪婪</div>
                <div className="font-mono text-slate-200">{mktStats.fearGreed}</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">BTC 佔比</div>
                <div className="font-mono text-slate-200">{mktStats.btcDominance}%</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">24h 爆倉</div>
                <div className="font-mono text-slate-200">{compactZh(mktStats.liq24h)}</div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
