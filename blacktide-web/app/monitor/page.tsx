"use client";

import { useFetch } from "@/lib/useFetch";
import { AlertItem } from "@/lib/types";
import { timeAgoZh } from "@/lib/format";
import PageHeader from "@/components/PageHeader";

interface Resp { alerts: AlertItem[] }

function sevMeta(s: AlertItem["severity"]) {
  if (s === "critical") return "border-l-down bg-down/5";
  if (s === "warn") return "border-l-amber-400 bg-amber-500/5";
  return "border-l-tide-500 bg-tide-500/5";
}

const TYPE_LABEL: Record<AlertItem["type"], string> = {
  whale: "🐋 巨鯨",
  flow: "💧 資金流",
  liquidation: "💥 爆倉",
  funding: "📊 資金費",
  volume: "📈 異常量",
};

export default function MonitorPage() {
  const { data } = useFetch<Resp>("/api/alerts", 12000);
  const alerts = data?.alerts ?? [];
  return (
    <div>
      <PageHeader title="監控 Monitor" subtitle="鏈上 / 爆倉 / 資金費 / 異常量警示（Mock · 屬未來強化，現階段不進決策）" right={<span className="text-[11px] text-slate-600">Mock</span>} />
      <div className="space-y-2.5">
        {alerts.map((a) => (
          <div key={a.id} className={"card border-l-2 p-3.5 " + sevMeta(a.severity)}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-100">{TYPE_LABEL[a.type]}</span>
                {a.symbol && <span className="rounded bg-ink-700 px-1.5 py-0.5 text-[11px] font-mono text-tide-300">{a.symbol}</span>}
              </div>
              <span className="text-[11px] text-slate-500">{timeAgoZh(a.time)}</span>
            </div>
            <div className="mt-1 text-sm font-medium text-slate-200">{a.title}</div>
            <div className="text-xs text-slate-500">{a.detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
