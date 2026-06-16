"use client";
import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useApp } from "@/lib/store";
import { X, Check, Minus } from "lucide-react";
import { PRICING, FEATURES } from "@/lib/access";
export default function PricingModal() {
  const { pricingOpen, setPricingOpen } = useApp();
  const { data: session } = useSession();
  const router = useRouter();
  const [cycle, setCycle] = useState<"monthly" | "yearly">("yearly");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  if (!pricingOpen) return null;
  const buy = async (tier: "air" | "pro") => {
    if (!session) { setPricingOpen(false); router.push("/login"); return; }
    setBusy(true); setMsg("");
    try {
      const r = await fetch("/api/checkout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tier, cycle }) });
      const d = await r.json();
      if (d.url) { window.location.href = d.url; return; }
      setMsg(d.message || d.error || "已送出");
    } catch { setMsg("結帳服務暫時無法使用，請稍後再試"); }
    finally { setBusy(false); }
  };
  const price = (t: "air" | "pro") => (cycle === "yearly" ? PRICING[t].yearly : PRICING[t].monthly);
  const unit = cycle === "yearly" ? "USD / 年" : "USD / 月";
  const Plan = ({ t, accent }: { t: "air" | "pro"; accent: string }) => (
    <div className={`rounded-xl border p-4 ${t === "pro" ? "border-amber-500/30 bg-amber-500/5" : "border-tide-500/30 bg-tide-500/5"}`}>
      <div className="flex items-center gap-2">
        <span className={`text-sm font-bold ${t === "pro" ? "text-amber-200" : "text-tide-200"}`}>{t === "pro" ? "Pro 會員" : "Air 會員"}</span>
        {cycle === "yearly" && <span className="rounded-full bg-white/10 px-1.5 py-0.5 text-[10px] text-slate-300">省 {PRICING[t].off}%</span>}
      </div>
      <div className="mt-2 font-mono text-2xl font-bold">{price(t)} <span className="text-sm font-normal text-slate-500">{unit}</span></div>
      <div className="mt-0.5 text-[11px] text-slate-500">{cycle === "yearly" ? "平均約 " + Math.round(PRICING[t].yearly / 12) + " USD / 月" : ""}</div>
      <div className="mt-1 text-[11px] text-slate-400">{t === "pro" ? "全部功能，含黑潮船長訊號與回測" : "解鎖分析、新聞、監控與全站圖表"}</div>
      <button disabled={busy} onClick={() => buy(t)} className={`mt-3 w-full rounded-lg py-2.5 text-sm font-semibold disabled:opacity-50 ${accent}`}>{busy ? "處理中…" : "選擇 " + (t === "pro" ? "Pro" : "Air")}</button>
    </div>
  );
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={() => setPricingOpen(false)} />
      <div className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 bg-ink-800 p-5">
        <div className="flex items-center">
          <div>
            <div className="text-base font-bold">選擇你的方案</div>
            <div className="mt-0.5 text-xs text-slate-500">Air 解鎖分析與資訊；Pro 解鎖黑潮船長訊號與回測</div>
          </div>
          <button onClick={() => setPricingOpen(false)} className="ml-auto rounded-lg p-1.5 text-slate-400 hover:bg-white/5"><X size={18} /></button>
        </div>
        <div className="mt-4 inline-flex rounded-lg bg-white/[0.04] p-1 text-xs font-semibold">
          {(["monthly", "yearly"] as const).map((c) => (
            <button key={c} onClick={() => setCycle(c)} className={`rounded-md px-3 py-1.5 transition-colors ${cycle === c ? "bg-tide-500/15 text-tide-300" : "text-slate-400"}`}>
              {c === "monthly" ? "月繳" : "年繳（更省）"}
            </button>
          ))}
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Plan t="air" accent="bg-tide-500/15 text-tide-300 hover:bg-tide-500/25" />
          <Plan t="pro" accent="bg-amber-500/20 text-amber-200 hover:bg-amber-500/30" />
        </div>
        <div className="mt-4 overflow-hidden rounded-xl border border-white/5">
          <div className="grid grid-cols-[1fr_56px_56px] border-b border-white/5 bg-white/[0.03] px-3 py-2 text-[11px] text-slate-400">
            <span>功能</span><span className="text-center text-tide-300">Air</span><span className="text-center text-amber-300">Pro</span>
          </div>
          {FEATURES.map((f) => (
            <div key={f.name} className="grid grid-cols-[1fr_56px_56px] items-center border-b border-white/5 px-3 py-2 text-xs last:border-0">
              <span className="text-slate-300">{f.name}</span>
              <span className="flex justify-center">{f.air ? <Check size={14} className="text-up" /> : <Minus size={14} className="text-slate-600" />}</span>
              <span className="flex justify-center">{f.pro ? <Check size={14} className="text-amber-300" /> : <Minus size={14} className="text-slate-600" />}</span>
            </div>
          ))}
        </div>
        {msg && <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">{msg}</div>}
        <div className="mt-3 text-[10px] leading-relaxed text-slate-600">支付方式：NOWPayments（USDT / BTC / ETH 等加密貨幣）。本服務為策略驗證期數據，不構成投資建議。</div>
      </div>
    </div>
  );
}
