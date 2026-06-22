"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Signal } from "@/lib/types";
import SignalCard from "@/components/SignalCard";
import SignalModal from "@/components/SignalModal";
import { C, MONO, SERIF } from "@/lib/theme";
import Corner from "@/components/site/Corner";
import { Crown, Radio, Send, Bell, ArrowRight, ExternalLink, Lock } from "lucide-react";
import { useApp } from "@/lib/store";
import { useSession } from "next-auth/react";

const TG_CHANNEL = "https://t.me/KuroshioSignal";
const TG_VIP = "https://t.me/+G1wwlviXQaE2NDRl";

function LiveFeed({ userTier }: { userTier: string }) {
  const [activeSignals, setActiveSignals] = useState<Signal[]>([]);
  const [prevCount, setPrevCount] = useState(-1);
  const [newSymbols, setNewSymbols] = useState<Set<string>>(new Set());
  const [liveSource, setLiveSource] = useState("");
  const [lastUpdate, setLastUpdate] = useState(0);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    fetch("/api/signals")
      .then((r) => r.json())
      .then((d) => {
        const active: Signal[] = (d.signals ?? []).filter((s: Signal) => s.status === "active");
        setActiveSignals(active);
        setLiveSource(d.source ?? "");
        setLastUpdate(Date.now());
        setLoading(false);
        setPrevCount((prev) => {
          if (prev >= 0 && active.length > prev) {
            const prevSymbols = new Set(activeSignals.map((s) => s.symbol));
            const fresh = new Set(active.filter((s) => !prevSymbols.has(s.symbol)).map((s) => s.symbol));
            if (fresh.size > 0) {
              setNewSymbols(fresh);
              setTimeout(() => setNewSymbols(new Set()), 30000);
            }
          }
          return active.length;
        });
      })
      .catch(() => { setLoading(false); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 15000);
    return () => clearInterval(iv);
  }, [refresh]);

  const relTime = (ts: number) => {
    if (!ts) return "";
    const s = Math.floor((Date.now() - ts) / 1000);
    if (s < 60) return s + "s 前";
    return Math.floor(s / 60) + "m 前";
  };

  const isLive = liveSource === "redis";

  return (
    <section style={{ position: "relative", overflow: "hidden", borderRadius: 18, padding: 20, border: `1px solid ${C.lineGold}`, background: "linear-gradient(180deg, rgba(16,30,48,0.7), rgba(6,16,30,0.55))" }}>
      <Corner pos="tl" /><Corner pos="tr" />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2">
          <span style={{ width: 8, height: 8, borderRadius: 99, background: isLive ? C.green : C.dim, boxShadow: isLive ? `0 0 6px ${C.green}` : "none", animation: isLive ? "pulseDot 1.5s infinite" : "none" }} />
          <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: 2, color: isLive ? C.green : C.dim }}>{isLive ? "LIVE · 即時持倉監控" : "DEMO · 展示模式"}</span>
          {lastUpdate > 0 && <span style={{ fontSize: 10.5, color: C.dim }}>更新 {relTime(lastUpdate)}</span>}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <a href={TG_CHANNEL} target="_blank" rel="noopener noreferrer" className="tg-btn flex items-center gap-1.5 rounded-lg px-2.5 py-1" style={{ fontSize: 11, fontWeight: 700, border: `1px solid ${C.teal}40`, background: "rgba(55,214,196,0.08)", color: C.teal }}>
            <Send size={11} /> 公開頻道
          </a>
          {userTier === "pro" ? (
            <a href={TG_VIP} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 rounded-lg px-2.5 py-1" style={{ fontSize: 11, fontWeight: 700, border: `1px solid ${C.gold}55`, background: "rgba(232,198,110,0.1)", color: C.gold }}>
              <Crown size={11} /> VIP 群
            </a>
          ) : (
            <span className="flex items-center gap-1 rounded-lg px-2.5 py-1" style={{ fontSize: 11, color: C.dim, border: `1px solid ${C.line}` }}>
              <Crown size={10} /> VIP 群（Pro）
            </span>
          )}
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">{[1, 2].map((i) => <div key={i} className="h-14 animate-pulse rounded-xl" style={{ background: "rgba(255,255,255,0.04)" }} />)}</div>
      ) : activeSignals.length > 0 ? (
        <div className="space-y-2">
          {activeSignals.map((sig) => {
            const isNew = newSymbols.has(sig.symbol);
            const hitCount = sig.tps?.filter((t) => t.hit).length ?? (sig as unknown as { tpHitCount?: number }).tpHitCount ?? 0;
            const locked = sig.entryLow == null;
            const sc = sig.direction === "long" ? C.green : C.rose;
            return (
              <div key={sig.id} className="sigrow" style={{ position: "relative", overflow: "hidden", borderRadius: 12, padding: "10px 12px", border: isNew ? `1px solid ${C.green}66` : `1px solid ${C.line}`, background: isNew ? "rgba(70,214,160,0.06)" : "rgba(255,255,255,0.02)" }}>
                <div className="flex flex-wrap items-center gap-2">
                  {isNew && <span style={{ fontSize: 9, fontWeight: 800, letterSpacing: 1, padding: "2px 7px", borderRadius: 99, color: C.green, background: "rgba(70,214,160,0.18)", animation: "pulseDot 1.4s infinite" }}>NEW</span>}
                  <span style={{ fontSize: 11, fontWeight: 700, color: sc }}>{sig.direction === "long" ? "▲ LONG" : "▼ SHORT"}</span>
                  <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 14, color: C.ink }}>{sig.symbol}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 6, color: sig.tier === "S" ? C.gold : C.mut, border: `1px solid ${sig.tier === "S" ? C.gold + "55" : C.line}` }}>Tier {sig.tier}</span>
                  {hitCount > 0 && <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 99, color: C.green, background: "rgba(70,214,160,0.15)" }}>TP{hitCount} 已達</span>}
                  <span style={{ marginLeft: "auto", fontSize: 10.5, color: C.dim }}>持倉中</span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-3" style={{ fontSize: 11 }}>
                  {!locked ? (
                    <>
                      <span style={{ color: C.dim }}>進場 <span style={{ fontFamily: MONO, color: C.ink }}>{sig.entryLow}</span></span>
                      {sig.tps?.[0] && <span style={{ color: sig.tps[0].hit ? C.green : C.dim, fontWeight: sig.tps[0].hit ? 700 : 400 }}>TP1 <span style={{ fontFamily: MONO }}>{sig.tps[0].price}</span>{sig.tps[0].hit ? " ✓" : ""}</span>}
                      {sig.tps?.[1] && <span style={{ color: sig.tps[1].hit ? C.green : C.dim, fontWeight: sig.tps[1].hit ? 700 : 400 }}>TP2 <span style={{ fontFamily: MONO }}>{sig.tps[1].price}</span>{sig.tps[1].hit ? " ✓" : ""}</span>}
                      {sig.tps?.[2] && <span style={{ color: sig.tps[2].hit ? C.green : C.dim, fontWeight: sig.tps[2].hit ? 700 : 400 }}>TP3 <span style={{ fontFamily: MONO }}>{sig.tps[2].price}</span>{sig.tps[2].hit ? " ✓" : ""}</span>}
                      <span style={{ color: C.dim }}>SL <span style={{ fontFamily: MONO, color: C.rose }}>{sig.stopLoss}</span></span>
                    </>
                  ) : (
                    <span style={{ display: "flex", alignItems: "center", gap: 5, color: C.dim }}><Lock size={11} />進場價位 · 止損 · 止盈 — 升級 Plus 解鎖</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-xl px-4 py-4" style={{ border: `1px solid ${C.line}`, fontSize: 13, color: C.dim }}>
          <span style={{ fontSize: 18 }}>📡</span>
          <div>
            <div style={{ fontWeight: 700, color: C.mut }}>目前無持倉信號</div>
            <div style={{ fontSize: 11, marginTop: 2 }}>持續掃描 52 幣種中，新信號出現時即時顯示</div>
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2" style={{ fontSize: 12 }}>
        <a href={TG_CHANNEL} target="_blank" rel="noopener noreferrer" className="tg-btn flex flex-1 items-center justify-center gap-1.5 rounded-xl px-3 py-2.5" style={{ fontWeight: 700, border: `1px solid ${C.teal}33`, background: "rgba(55,214,196,0.06)", color: C.teal }}>
          <Bell size={13} /> 訂閱 Telegram 推播通知<ArrowRight size={11} className="ml-auto" />
        </a>
        {userTier === "pro" && (
          <a href={TG_VIP} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 rounded-xl px-4 py-2.5" style={{ fontWeight: 700, border: `1px solid ${C.gold}40`, background: "rgba(232,198,110,0.08)", color: C.gold }}>
            <Crown size={13} /> 進入 VIP 群<ExternalLink size={11} className="ml-1" />
          </a>
        )}
      </div>
    </section>
  );
}

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
      {/* 黑潮船長 CTA */}
      <section style={{ position: "relative", overflow: "hidden", borderRadius: 18, padding: 22, border: `1px solid ${C.lineGold}`, background: "linear-gradient(135deg, rgba(232,198,110,0.1), rgba(10,12,18,0.5))" }}>
        <Corner pos="tl" /><Corner pos="br" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="mb-1.5 flex items-center gap-2">
              <Radio size={14} color={C.gold} />
              <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2, color: C.gold2 }}>黑潮船長 · 信號中心</span>
            </div>
            <h1 className="gold-text" style={{ fontFamily: SERIF, fontSize: 24, fontWeight: 700, letterSpacing: 0.5 }}>黑潮 BLACKTIDE · 交易信號</h1>
            <p className="mt-1.5 max-w-md" style={{ fontSize: 13.5, lineHeight: 1.7, color: C.mut }}>
              七大技術策略加新聞情緒投票，過五維評分與盈虧比硬門檻才出手。三段止盈 40/35/25，波動自適應止損。
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:shrink-0 sm:flex-row sm:items-center sm:gap-3">
            {userTier === "free" ? (
              <button onClick={() => setPricingOpen(true)} className="cta flex items-center justify-center gap-1.5 rounded-xl px-6 py-3" style={{ fontSize: 14, fontWeight: 800, color: C.abyss, background: `linear-gradient(135deg,#FFF4D2,${C.gold} 45%,${C.gold2})` }}>
                <Crown size={15} /> 加入船長艙
              </button>
            ) : (
              <div className="inline-flex items-center gap-1.5 rounded-xl px-4 py-2.5" style={{ fontSize: 13.5, fontWeight: 700, border: `1px solid ${C.gold}40`, background: "rgba(232,198,110,0.08)", color: C.gold }}>
                <Crown size={14} /> 已訂閱 · 完整信號解鎖
              </div>
            )}
          </div>
        </div>
      </section>

      <LiveFeed userTier={userTier} />

      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: C.ink }}>黑潮船長 · 信號中心</h2>
          <p className="mt-0.5" style={{ fontSize: 11.5, color: C.dim }}>進出場計畫、分批止盈與動態止損</p>
        </div>
        <span style={{ fontSize: 10.5, fontWeight: 700, padding: "3px 9px", borderRadius: 99, color: source === "redis" ? C.green : C.gold, background: source === "redis" ? "rgba(70,214,160,0.12)" : "rgba(232,198,110,0.1)" }}>
          {source === "redis" ? "Bot 即時資料" : "展示資料"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[["信號總數", String(signals.length), C.ink], ["進行中", String(signals.filter((s) => s.status === "active").length), C.ink], ["做多", String(longN), C.green], ["做空", String(shortN), C.rose]].map(([label, value, color]) => (
          <div key={label} className="rounded-xl p-3.5" style={{ border: `1px solid ${C.line}`, background: "rgba(255,255,255,0.02)" }}>
            <div style={{ fontSize: 11, color: C.dim }}>{label}</div>
            <div style={{ marginTop: 4, fontFamily: MONO, fontSize: 19, fontWeight: 800, color: color as string }}>{value}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {(["all", "long", "short"] as const).map((d) => (
          <button key={d} onClick={() => setDir(d)} className="rounded-full px-3 py-1" style={{ fontSize: 12, border: `1px solid ${dir === d ? C.gold + "70" : C.line}`, background: dir === d ? "rgba(232,198,110,0.12)" : "transparent", color: dir === d ? C.gold : C.mut }}>
            {d === "all" ? "全部" : d === "long" ? "做多" : "做空"}
          </button>
        ))}
        <span style={{ margin: "0 4px", width: 1, height: 16, background: C.line }} />
        {["all", "S", "A", "B", "C"].map((t) => (
          <button key={t} onClick={() => setTier(t)} className="rounded-full px-3 py-1" style={{ fontSize: 12, border: `1px solid ${tier === t ? C.gold + "70" : C.line}`, background: tier === t ? "rgba(232,198,110,0.12)" : "transparent", color: tier === t ? C.gold : C.mut }}>
            {t === "all" ? "全部 Tier" : "Tier " + t}
          </button>
        ))}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜尋幣種…" className="ml-auto w-32 rounded-lg px-3 py-1.5 text-sm outline-none"
          style={{ border: `1px solid ${C.line}`, background: "rgba(255,255,255,0.02)", color: C.ink }} />
      </div>

      {loading && <div className="h-28 animate-pulse rounded-xl" style={{ background: "rgba(255,255,255,0.04)" }} />}
      {!loading && filtered.length === 0 && <div className="rounded-xl p-8 text-center" style={{ border: `1px solid ${C.line}`, fontSize: 13, color: C.dim }}>沒有符合條件的信號</div>}
      <div className="grid gap-4 lg:grid-cols-2">
        {filtered.map((s) => <SignalCard key={s.id} s={s} onOpen={() => setOpen(s)} />)}
      </div>
      {open && <SignalModal s={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
