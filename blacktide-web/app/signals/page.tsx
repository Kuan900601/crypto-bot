"use client";
import { useEffect, useMemo, useState } from "react";
import { Signal } from "@/lib/types";
import SignalCard from "@/components/SignalCard";
import SignalModal from "@/components/SignalModal";
import { SectionTitle, Chip, Stat, Badge } from "@/components/ui";
import { Crown, Radio } from "lucide-react";
import { useApp } from "@/lib/store";
import { useSession } from "next-auth/react";
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
  const { setPricingOpen } = useApp();
  const { data: session } = useSession();
  const userTier = (session?.user?.tier as string) || "free";
  const longN = signals.filter((s) => s.direction === "long").length;
  const shortN = signals.filter((s) => s.direction === "short").length;
  return (
    <div className="space-y-5">
      {/* 黑潮船長 CTA — 金色卡片，置頂 */}
      <section className="relative overflow-hidden rounded-2xl border border-amber-500/25 p-5 sm:p-6"
        style={{ background: "linear-gradient(135deg, rgba(212,175,55,0.12), rgba(10,12,18,0.5))" }}>
        <div className="pointer-events-none absolute -right-10 -top-10 h-48 w-48 rounded-full bg-amber-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -left-6 bottom-0 h-32 w-32 rounded-full bg-tide-400/10 blur-2xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="mb-1.5 flex items-center gap-2">
              <Radio size={14} className="text-amber-400" />
              <span className="text-[10px] font-semibold uppercase tracking-widest text-amber-400/80">黑潮船長 · 信號中心</span>
            </div>
            <h1 className="font-display text-2xl font-bold text-gold glow-gold">黑潮 BLACKTIDE · 交易信號</h1>
            <p className="mt-1.5 max-w-md text-sm leading-relaxed text-slate-400">
              七大技術策略加新聞情緒投票，過五維評分與盈虧比硬門檻才出手。三段止盈 40/35/25，波動自適應止損。
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:shrink-0 sm:flex-row sm:items-center sm:gap-3">
            {userTier === "free" ? (
              <button onClick={() => setPricingOpen(true)}
                className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-tide-400 to-tide-600 px-6 py-3 text-sm font-bold text-ink-950 shadow-lg shadow-tide-500/25 hover:opacity-90">
                <Crown size={15} /> 加入船長艙
              </button>
            ) : (
              <div className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm font-semibold text-amber-300">
                <Crown size={14} /> 已訂閱 · 完整信號解鎖
              </div>
            )}
          </div>
        </div>
      </section>
      <SectionTitle title="黑潮船長 · 信號中心" desc="進出場計畫、分批止盈與動態止損"
        right={source === "redis" ? <Badge tone="up">Bot 即時資料</Badge> : <Badge tone="amber">展示資料</Badge>} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="信號總數" value={String(signals.length)} />
        <Stat label="進行中" value={String(signals.filter((s) => s.status === "active").length)} />
        <Stat label="做多" value={String(longN)} tone="up" />
        <Stat label="做空" value={String(shortN)} tone="down" />
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
