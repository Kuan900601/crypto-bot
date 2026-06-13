"use client";
import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useApp } from "@/lib/store";
import { X, Check, Minus } from "lucide-react";
const YEARLY_BADGE = "限時 85% OFF";
const FEATURES = [
  { name: "市場總覽（Bybit 即時行情）", free: true },
  { name: "黑潮船長即時訊號", free: false },
  { name: "AI 智能分析", free: false },
  { name: "即時新聞 + 情緒分析", free: false },
  { name: "異常監控 / 巨鯨警報", free: false },
  { name: "策略回測", free: false },
  { name: "Telegram 推播", free: false },
];
export default function PricingModal() {
  const { pricingOpen, setPricingOpen } = useApp();
  const { data: session } = useSession();
  const router = useRouter();
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  if (!pricingOpen) return null;
  const buy = async (plan: "monthly" | "yearly") => {
    if (!session) { setPricingOpen(false); router.push("/login"); return; }
    setBusy(true); setMsg("");
    try {
      const r = await fetch("/api/checkout", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      const d = await r.json();
      setMsg(d.message || d.error || "已送出");
    } catch { setMsg("結帳服務暫時無法使用，請稍後再試"); }
    finally { setBusy(false); }
  };
  const btn = "mt-4 w-full rounded-lg py-2.5 text-sm font-semibold transition-colors disabled:opacity-50";
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={() => setPricingOpen(false)} />
      <div className="relative max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 bg-ink-800 p-5">
        <div className="flex items-center">
          <div>
            <div className="font-display text-base font-bold text-gold">升級黑潮會員</div>
            <div className="mt-0.5 text-xs text-slate-500">解鎖黑潮船長即時訊號與全部進階功能</div>
          </div>
          <button onClick={() => setPricingOpen(false)} className="ml-auto rounded-lg p-1.5 text-slate-400 hover:bg-white/5"><X size={18} /></button>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <div className="text-sm font-semibold">月費方案</div>
            <div className="mt-2 font-mono text-2xl font-bold">199 <span className="text-sm font-normal text-slate-500">TWD / 月</span></div>
            <button disabled={busy} onClick={() => buy("monthly")} className={`${btn} bg-tide-500/15 text-tide-300 hover:bg-tide-500/25`}>選擇月費</button>
          </div>
          <div className="relative rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
            <span className="absolute -top-2.5 right-3 rounded-full bg-amber-400 px-2 py-0.5 text-[10px] font-bold text-ink-950">{YEARLY_BADGE}</span>
            <div className="text-sm font-semibold text-amber-200">年費方案</div>
            <div className="mt-2 font-mono text-2xl font-bold">2029 <span className="text-sm font-normal text-slate-500">TWD / 年</span></div>
            <button disabled={busy} onClick={() => buy("yearly")} className={`${btn} bg-amber-500/20 text-amber-200 hover:bg-amber-500/30`}>選擇年費</button>
          </div>
        </div>
        <div className="mt-4 overflow-hidden rounded-xl border border-white/5">
          <div className="grid grid-cols-[1fr_64px_64px] border-b border-white/5 bg-white/[0.03] px-3 py-2 text-[11px] text-slate-400">
            <span>功能</span><span className="text-center">Free</span><span className="text-center">Premium</span>
          </div>
          {FEATURES.map((f) => (
            <div key={f.name} className="grid grid-cols-[1fr_64px_64px] items-center border-b border-white/5 px-3 py-2 text-xs last:border-0">
              <span className="text-slate-300">{f.name}</span>
              <span className="flex justify-center">{f.free ? <Check size={14} className="text-up" /> : <Minus size={14} className="text-slate-600" />}</span>
              <span className="flex justify-center"><Check size={14} className="text-amber-300" /></span>
            </div>
          ))}
        </div>
        {msg && <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">{msg}</div>}
        <div className="mt-3 text-[10px] text-slate-600">支付方式：NOWPayments（USDT / BTC / ETH 等加密貨幣）。本服務為策略驗證期數據，不構成投資建議。</div>
      </div>
    </div>
  );
}
