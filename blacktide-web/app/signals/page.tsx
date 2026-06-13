"use client";
import { useEffect, useMemo, useState } from "react";
import { Signal } from "@/lib/types";
import SignalCard from "@/components/SignalCard";
import SignalModal from "@/components/SignalModal";
import { SectionTitle, Chip, Stat, Badge } from "@/components/ui";
export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [source, setSource] = useState("mock");
  const [loading, setLoading] = useState(true);
  const [dir, setDir] = useState<"all" | "long" | "short">("all");
  const [tier, setTier] = useState<string>("all");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Signal | null>(null);
  useEffect(() => {
    fetch("/api/signals").then((r) => r.json()).then((d) => { setSignals(d.signals); setSource(d.source); }).catch(() => {}).finally(() => setLoading(false));
  }, []);
  const filtered = useMemo(() => signals.filter((s) =>
    (dir === "all" || s.direction === dir) &&
    (tier === "all" || s.tier === tier) &&
    (!q || s.symbol.toLowerCase().includes(q.toLowerCase()))
  ), [signals, dir, tier, q]);
  const closed = signals.filter((s) => s.status !== "active" && s.finalPct !== undefined);
  const wins = closed.filter((s) => (s.finalPct ?? 0) > 0).length;
  const winRate = closed.length ? Math.round((wins / closed.length) * 100) : 0;
  const ev = closed.length ? closed.reduce((a, s) => a + (s.finalPct ?? 0), 0) / closed.length : 0;
  return (
    <div className="space-y-5">
      <SectionTitle title="黑潮船長" desc="進出場計畫、分批止盈與歷史結算"
        right={source === "redis" ? <Badge tone="up">Bot 即時資料</Badge> : <Badge tone="amber">展示資料</Badge>} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="信號總數" value={String(signals.length)} />
        <Stat label="進行中" value={String(signals.filter((s) => s.status === "active").length)} />
        <Stat label="已結算勝率" value={winRate + "%"} sub={`${wins}/${closed.length} 筆`} />
        <Stat label="平均結算（期望值）" value={`${ev >= 0 ? "+" : ""}${ev.toFixed(2)}%`} sub="樣本小僅供參考" tone={ev >= 0 ? "up" : "down"} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Chip active={dir === "all"} onClick={() => setDir("all")}>全部</Chip>
        <Chip active={dir === "long"} onClick={() => setDir("long")}>做多</Chip>
        <Chip active={dir === "short"} onClick={() => setDir("short")}>做空</Chip>
        <span className="mx-1 h-4 w-px bg-white/10" />
        {["all", "S", "A", "B", "C"].map((t) => (
          <Chip key={t} active={tier === t} onClick={() => setTier(t)}>{t === "all" ? "全部 Tier" : "Tier " + t}</Chip>
        ))}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜尋幣種…"
          className="ml-auto w-32 rounded-lg border border-white/5 bg-ink-800 px-3 py-1.5 text-sm outline-none focus:border-tide-500/40" />
      </div>
      {loading && <div className="h-28 animate-pulse rounded-xl bg-white/5" />}
      {!loading && filtered.length === 0 && <div className="rounded-xl border border-white/5 p-8 text-center text-sm text-slate-500">沒有符合條件的信號</div>}
      <div className="grid gap-4 lg:grid-cols-2">
        {filtered.map((s) => <SignalCard key={s.id} s={s} onOpen={() => setOpen(s)} />)}
      </div>
      {open && <SignalModal s={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
