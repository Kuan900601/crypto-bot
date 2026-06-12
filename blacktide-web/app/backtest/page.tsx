"use client";

import { useFetch } from "@/lib/useFetch";
import { SignalsResponse } from "@/lib/types";
import { fmtPct } from "@/lib/format";
import StatCard from "@/components/StatCard";
import PageHeader from "@/components/PageHeader";
import { SourceBadge, TierBadge } from "@/components/Badges";
import { Tier } from "@/lib/types";

export default function BacktestPage() {
  const { data } = useFetch<SignalsResponse>("/api/signals", 20000);
  const stats = data?.stats;
  const history = data?.history ?? [];

  // 依 tier 分組
  const tiers: Tier[] = ["S", "A", "B", "C"];
  const byTier = tiers.map((t) => {
    const rows = history.filter((h) => h.tier === t);
    const n = rows.length;
    const wins = rows.filter((h) => (h.finalPct ?? 0) > 0).length;
    const ev = n ? rows.reduce((a, h) => a + (h.finalPct ?? 0), 0) / n : 0;
    return { t, n, winRate: n ? (wins / n) * 100 : 0, ev };
  });

  // 驗證門檻判斷（CLAUDE.md 第 10 節）
  const passN = (stats?.n ?? 0) >= 50;
  const passEv = (stats?.ev ?? 0) >= 0.4;
  const passRatio = stats ? stats.avgWin > Math.abs(stats.avgLoss) : false;

  return (
    <div>
      <PageHeader
        title="驗證 Edge"
        subtitle="期望值驗證儀表 · 與 bot /edge 同口徑（final_pct 為毛價格 %，未扣成本）"
        right={data && <SourceBadge source={data.source} error={data.error} />}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="樣本數" value={stats?.n ?? "—"} sub="目標 ≥ 50 筆" tone={passN ? "up" : "neutral"} />
        <StatCard label="毛期望值 / 筆" value={stats ? fmtPct(stats.ev) : "—"} sub="可交易 ≥ +0.3~0.4%" tone={stats ? (stats.ev > 0 ? "up" : "down") : "neutral"} />
        <StatCard label="勝率" value={stats ? stats.winRate.toFixed(1) + "%" : "—"} sub={stats ? `Wilson 下界 ${stats.wilsonLb.toFixed(1)}%` : ""} />
        <StatCard label="最大連虧" value={stats?.maxLossStreak ?? "—"} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-300">驗證門檻（約 50 筆乾淨交易）</h2>
          <ul className="space-y-2 text-sm">
            <Gate ok={passN} label={`樣本數 ≥ 50（目前 ${stats?.n ?? 0}）`} />
            <Gate ok={passEv} label={`毛期望值 ≥ +0.4%（目前 ${stats ? fmtPct(stats.ev) : "—"}）`} />
            <Gate ok={passRatio} label="平均盈 > 平均虧" />
            <Gate ok={false} label="零爆倉（需真實執行驗證，非 SIM 可判定）" muted />
          </ul>
          <p className="mt-3 text-xs leading-relaxed text-slate-500">
            提醒：正期望的 SIM 是<strong className="text-slate-400">必要、非充分</strong>條件。通過後仍要先驗證真實執行對得上，才談真錢。30 筆只是「第一眼」。
          </p>
        </section>

        <section className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-300">分 Tier 統計</h2>
          <div className="overflow-hidden rounded-lg border border-ink-700">
            <table className="w-full text-sm">
              <thead className="bg-ink-800 text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-3 py-2 text-left">Tier</th>
                  <th className="px-3 py-2 text-right">樣本</th>
                  <th className="px-3 py-2 text-right">勝率</th>
                  <th className="px-3 py-2 text-right">毛 EV</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-700">
                {byTier.map((r) => (
                  <tr key={r.t}>
                    <td className="px-3 py-2"><TierBadge t={r.t} /></td>
                    <td className="px-3 py-2 text-right font-mono text-slate-300">{r.n}</td>
                    <td className="px-3 py-2 text-right font-mono text-slate-300">{r.n ? r.winRate.toFixed(0) + "%" : "—"}</td>
                    <td className={"px-3 py-2 text-right font-mono " + (r.ev > 0 ? "text-up" : r.ev < 0 ? "text-down" : "text-slate-500")}>
                      {r.n ? fmtPct(r.ev) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

function Gate({ ok, label, muted }: { ok: boolean; label: string; muted?: boolean }) {
  return (
    <li className="flex items-center gap-2">
      <span className={"grid h-5 w-5 place-items-center rounded-full text-[11px] " + (muted ? "bg-ink-700 text-slate-500" : ok ? "bg-up/20 text-up" : "bg-down/20 text-down")}>
        {muted ? "—" : ok ? "✓" : "✕"}
      </span>
      <span className={muted ? "text-slate-500" : "text-slate-300"}>{label}</span>
    </li>
  );
}
