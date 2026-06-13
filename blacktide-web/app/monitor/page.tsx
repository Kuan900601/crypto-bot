"use client";
import { useEffect, useState } from "react";
import { AlertItem } from "@/lib/types";
import { randomAlert } from "@/lib/mock";
import { useApp } from "@/lib/store";
import { SectionTitle, Card, Badge, Chip } from "@/components/ui";
import { Pause, Play, Waves, ArrowDownToLine, Flame, Zap, BarChart3 } from "lucide-react";
const META = {
  whale: { label: "巨鯨異動", icon: Waves, color: "text-tide-300" },
  flow: { label: "交易所流向", icon: ArrowDownToLine, color: "text-indigo-300" },
  liquidation: { label: "爆倉 / 清算", icon: Flame, color: "text-down" },
  funding: { label: "資金費率", icon: Zap, color: "text-amber-300" },
  volume: { label: "巨量成交", icon: BarChart3, color: "text-up" },
} as const;
const SEV: Record<AlertItem["severity"], { label: string; tone: "slate" | "amber" | "down" }> = {
  info: { label: "提示", tone: "slate" }, warn: { label: "警告", tone: "amber" }, critical: { label: "嚴重", tone: "down" },
};
export default function MonitorPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [live, setLive] = useState(true);
  const [type, setType] = useState<"all" | AlertItem["type"]>("all");
  const pushNotif = useApp((s) => s.pushNotif);
  useEffect(() => { fetch("/api/alerts").then((r) => r.json()).then((d) => setAlerts(d.alerts)).catch(() => {}); }, []);
  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => {
      const a = randomAlert();
      setAlerts((prev) => [a, ...prev].slice(0, 50));
      if (a.severity !== "info") pushNotif({ id: a.id, title: "異常警報：" + META[a.type].label, body: a.title, time: a.time });
    }, 7000);
    return () => clearInterval(id);
  }, [live, pushNotif]);
  const filtered = alerts.filter((a) => type === "all" || a.type === type);
  return (
    <div className="space-y-5">
      <SectionTitle title="異常監控" desc="巨鯨、流向、清算、費率與巨量事件（DEMO 模擬即時流）"
        right={
          <button onClick={() => setLive((v) => !v)}
            className="flex items-center gap-2 rounded-full border border-white/10 px-3 py-1.5 text-xs">
            {live ? <><span className="pulse-dot h-2 w-2 rounded-full bg-up" />即時監控中<Pause size={13} /></> : <>已暫停<Play size={13} /></>}
          </button>
        } />
      <div className="flex flex-wrap gap-2">
        <Chip active={type === "all"} onClick={() => setType("all")}>全部</Chip>
        {(Object.keys(META) as (keyof typeof META)[]).map((k) => (
          <Chip key={k} active={type === k} onClick={() => setType(k)}>{META[k].label}</Chip>
        ))}
      </div>
      <div className="space-y-2.5">
        {filtered.length === 0 && <div className="rounded-xl border border-white/5 p-8 text-center text-sm text-slate-500">沒有符合條件的事件</div>}
        {filtered.map((a) => {
          const Icon = META[a.type].icon;
          return (
            <Card key={a.id} className="flex items-start gap-3 p-3.5">
              <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/5 ${META[a.type].color}`}>
                <Icon size={16} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold">{a.title}</span>
                  <Badge tone={SEV[a.severity].tone}>{SEV[a.severity].label}</Badge>
                  {a.symbol && <Badge tone="tide">{a.symbol}</Badge>}
                  <span className="ml-auto shrink-0 font-mono text-[11px] text-slate-500">{a.time}</span>
                </div>
                <p className="mt-1 text-xs text-slate-400">{a.detail}</p>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
