"use client";

import { useState } from "react";
import { AnalysisItem } from "@/lib/types";
import { fmtPrice } from "@/lib/format";
import PageHeader from "@/components/PageHeader";
import PriceChart from "@/components/PriceChart";
import { ANALYSIS } from "@/lib/mock";
import { COINS } from "@/lib/bybit";

export default function AnalysisPage() {
  // K 線為 Bybit 即時；下方多空偏向/價位/建議仍為 mock，驗證通過後可接 analyzer 輸出。
  const [symbol, setSymbol] = useState("BTC");
  return (
    <div>
      <PageHeader title="分析 Analysis" subtitle="K 線為 Bybit 即時行情；偏向與操作建議為 Mock（驗證通過後接 analyzer）" right={<span className="text-[11px] text-slate-600">K 線即時 · 分析 Mock</span>} />

      <div className="mb-3 flex flex-wrap gap-1">
        {COINS.map((c) => (
          <button
            key={c.symbol}
            onClick={() => setSymbol(c.symbol)}
            className={
              "rounded-md px-2.5 py-1 text-xs font-semibold " +
              (symbol === c.symbol ? "bg-tide-500/20 text-tide-300" : "text-slate-400 hover:text-slate-200")
            }
          >
            {c.symbol}
          </button>
        ))}
      </div>

      <div className="mb-6">
        <PriceChart symbol={symbol} />
      </div>

      <AnalysisGrid />
    </div>
  );
}

function biasMeta(b: AnalysisItem["bias"]) {
  if (b === "long") return { txt: "偏多", cls: "text-up bg-up/10" };
  if (b === "short") return { txt: "偏空", cls: "text-down bg-down/10" };
  return { txt: "中性", cls: "text-slate-300 bg-slate-500/10" };
}

function AnalysisGrid() {
  const items: AnalysisItem[] = ANALYSIS;
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {items.map((a) => {
        const m = biasMeta(a.bias);
        return (
          <div key={a.symbol} className="card p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold text-slate-100">{a.symbol}</span>
                <span className={"rounded-md px-1.5 py-0.5 text-[11px] font-semibold " + m.cls}>{m.txt}</span>
              </div>
              <div className="text-right">
                <div className="text-[10px] text-slate-500">信心 / 風險</div>
                <div className="font-mono text-sm text-slate-200">{a.confidence} / {a.risk}</div>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="mb-1 text-[10px] text-slate-500">支撐</div>
                <div className="flex flex-wrap gap-1">
                  {a.support.map((p) => (
                    <span key={p} className="rounded bg-up/10 px-1.5 py-0.5 font-mono text-xs text-up">{fmtPrice(p)}</span>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-1 text-[10px] text-slate-500">阻力</div>
                <div className="flex flex-wrap gap-1">
                  {a.resistance.map((p) => (
                    <span key={p} className="rounded bg-down/10 px-1.5 py-0.5 font-mono text-xs text-down">{fmtPrice(p)}</span>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-3 rounded-lg bg-ink-800 p-2.5 text-sm text-slate-300">{a.action}</div>

            <ul className="mt-3 space-y-1 text-xs text-slate-500">
              {a.basis.map((b, i) => (
                <li key={i} className="flex gap-1.5"><span className="text-tide-500">·</span>{b}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
