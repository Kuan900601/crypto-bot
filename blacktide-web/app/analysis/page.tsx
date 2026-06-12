"use client";

import { AnalysisItem } from "@/lib/types";
import { fmtPrice } from "@/lib/format";
import PageHeader from "@/components/PageHeader";
import { ANALYSIS } from "@/lib/mock";

export default function AnalysisPage() {
  // 分析資料目前為 mock（由 lib/mock 提供）；驗證通過後可接 analyzer 輸出。
  return (
    <div>
      <PageHeader title="分析 Analysis" subtitle="多幣種多空偏向、關鍵價位與操作建議（Mock · 驗證通過後可接 analyzer 輸出）" right={<span className="text-[11px] text-slate-600">Mock</span>} />
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
