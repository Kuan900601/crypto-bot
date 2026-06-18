"use client";
import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useApp } from "@/lib/store";
import { X, Check, Minus, Send, ArrowRight, Zap, Crown, Shield } from "lucide-react";
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

  const monthlyPrice = (t: "air" | "pro") => PRICING[t].monthly;
  const yearlyPrice = (t: "air" | "pro") => PRICING[t].yearly;
  const monthlyEq = (t: "air" | "pro") => Math.round(PRICING[t].yearly / 12);
  const dailyEq = (t: "air" | "pro") => (PRICING[t].yearly / 365).toFixed(2);
  const yearlySave = (t: "air" | "pro") => PRICING[t].monthly * 12 - PRICING[t].yearly;

  const Plan = ({ t, accent, highlight }: { t: "air" | "pro"; accent: string; highlight?: boolean }) => (
    <div className={`relative rounded-2xl border p-5 transition-all ${highlight ? "border-amber-500/40 bg-gradient-to-b from-amber-500/[0.08] to-transparent shadow-xl shadow-amber-500/10 scale-[1.02]" : "border-tide-500/25 bg-tide-500/[0.04]"}`}>
      {highlight && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-amber-400 to-amber-600 px-3 py-0.5 text-[10px] font-bold text-ink-950">
          最受歡迎
        </div>
      )}
      {/* Plan header */}
      <div className="flex items-center gap-2">
        {highlight ? <Crown size={15} className="text-amber-400" /> : <Zap size={15} className="text-tide-400" />}
        <span className={`font-bold ${highlight ? "text-amber-200" : "text-tide-200"}`}>{t === "pro" ? "Pro 會員" : "Plus 會員"}</span>
        {cycle === "yearly" && (
          <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-bold ${highlight ? "bg-amber-500/20 text-amber-300" : "bg-tide-500/20 text-tide-300"}`}>
            省 {PRICING[t].off}%
          </span>
        )}
      </div>

      {/* Price display */}
      {cycle === "yearly" ? (
        <div className="mt-3">
          <div className="flex items-baseline gap-1.5">
            <span className="font-mono text-4xl font-bold">${yearlyPrice(t)}</span>
            <span className="text-sm text-slate-500">/ 年</span>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="font-mono text-base text-slate-400">${monthlyEq(t)} / 月均</span>
            <span className="text-[11px] text-slate-600">每天只要 ${dailyEq(t)}</span>
          </div>
          <div className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${highlight ? "bg-amber-500/15 text-amber-300" : "bg-tide-500/15 text-tide-300"}`}>
            比月繳省 ${yearlySave(t)}
          </div>
        </div>
      ) : (
        <div className="mt-3">
          <div className="flex items-baseline gap-1.5">
            <span className="font-mono text-4xl font-bold">${monthlyPrice(t)}</span>
            <span className="text-sm text-slate-500">/ 月</span>
          </div>
          <div className="mt-1 text-[11px] text-slate-500">選年繳省 {PRICING[t].off}%（省 ${Math.round(yearlySave(t))} 元）</div>
        </div>
      )}

      <div className="my-4 border-t border-white/5" />
      <div className="space-y-2 text-[12px] text-slate-300">
        {t === "pro" ? (
          <>
            <div className="flex items-center gap-2"><Check size={13} className="text-amber-400 shrink-0" /> 黑潮船長完整訊號（進出場計畫）</div>
            <div className="flex items-center gap-2"><Check size={13} className="text-amber-400 shrink-0" /> 策略回測工具（12 標的 × 8 策略）</div>
            <div className="flex items-center gap-2"><Check size={13} className="text-amber-400 shrink-0" /> AI 深度分析 + OI + 資金費率</div>
            <div className="flex items-center gap-2"><Check size={13} className="text-amber-400 shrink-0" /> 即時新聞中心 + 事件行事曆</div>
            <div className="flex items-center gap-2"><Check size={13} className="text-amber-400 shrink-0" /> 異常監控 + 美股分析</div>
            <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 px-2 py-1">
              <Check size={13} className="text-amber-300 shrink-0" />
              <span className="text-amber-200 font-semibold">黑潮 VIP 私密群（Telegram Pro 專屬）</span>
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2"><Check size={13} className="text-tide-400 shrink-0" /> AI 即時分析（RSI + OI + 資金費率）</div>
            <div className="flex items-center gap-2"><Check size={13} className="text-tide-400 shrink-0" /> 即時新聞中心（中英文）</div>
            <div className="flex items-center gap-2"><Check size={13} className="text-tide-400 shrink-0" /> 異常監控 + 美股分析</div>
            <div className="flex items-center gap-2"><Check size={13} className="text-tide-400 shrink-0" /> 事件行事曆 + 全站圖表</div>
            <div className="flex items-center gap-2"><Minus size={13} className="text-slate-600 shrink-0" /> 不含黑潮船長訊號（需 Pro）</div>
            <div className="flex items-center gap-2"><Minus size={13} className="text-slate-600 shrink-0" /> 不含 VIP 私密群（需 Pro）</div>
          </>
        )}
      </div>

      <button
        disabled={busy}
        onClick={() => buy(t)}
        className={`mt-4 w-full rounded-xl py-3 text-sm font-bold transition-all disabled:opacity-50 ${highlight ? "bg-gradient-to-r from-amber-400 to-amber-600 text-ink-950 hover:opacity-90 shadow-lg shadow-amber-500/20" : "bg-gradient-to-r from-tide-400 to-tide-600 text-ink-950 hover:opacity-90"}`}
      >
        {busy ? "處理中…" : `立即訂閱 ${t === "pro" ? "Pro" : "Plus"}`}
      </button>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 backdrop-blur-md bg-ink-950/60" onClick={() => setPricingOpen(false)} />
      <div className="pop-in relative max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 bg-ink-800 p-5 shadow-2xl">
        {/* Header */}
        <div className="flex items-center">
          <div>
            <div className="text-base font-bold">解鎖黑潮 BLACKTIDE</div>
            <div className="mt-0.5 text-xs text-slate-500">選擇方案 · 即時開通 · 加密貨幣付款</div>
          </div>
          <button onClick={() => setPricingOpen(false)} className="ml-auto rounded-lg p-1.5 text-slate-400 hover:bg-white/5"><X size={18} /></button>
        </div>

        {/* Trust badges */}
        <div className="mt-4 flex flex-wrap gap-2">
          {[
            { icon: Shield, text: "即時開通，無等待" },
            { icon: Zap, text: "52 幣種 · 7+1 策略" },
            { icon: Crown, text: "Telegram 公開記錄" },
          ].map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-center gap-1.5 rounded-full border border-white/5 bg-white/[0.03] px-3 py-1.5 text-[11px] text-slate-400">
              <Icon size={11} className="text-tide-400" /> {text}
            </div>
          ))}
        </div>

        {/* Cycle toggle */}
        <div className="mt-4 flex items-center gap-3">
          <div className="inline-flex rounded-xl bg-white/[0.04] p-1 text-xs font-semibold">
            {(["monthly", "yearly"] as const).map((c) => (
              <button key={c} onClick={() => setCycle(c)} className={`rounded-lg px-4 py-2 transition-colors ${cycle === c ? "bg-tide-500/20 text-tide-300 shadow-sm" : "text-slate-400 hover:text-slate-200"}`}>
                {c === "monthly" ? "月繳" : "年繳"}
              </button>
            ))}
          </div>
          {cycle === "yearly" && (
            <span className="rounded-full bg-up/15 px-2.5 py-1 text-[11px] font-bold text-up">年繳最省 30%</span>
          )}
        </div>

        {/* Plan cards */}
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Plan t="air" accent="tide" />
          <Plan t="pro" accent="amber" highlight />
        </div>

        {/* Feature comparison table */}
        <div className="mt-5 overflow-hidden rounded-xl border border-white/5">
          <div className="grid grid-cols-[1fr_56px_56px] border-b border-white/5 bg-white/[0.03] px-3 py-2 text-[11px] text-slate-400">
            <span>功能對比</span><span className="text-center text-tide-300">Plus</span><span className="text-center text-amber-300">Pro</span>
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

        {/* Transparency CTA */}
        <a href="https://t.me/KuroshioSignal" target="_blank" rel="noopener noreferrer"
          className="mt-4 flex items-center gap-3 rounded-xl border border-tide-500/15 bg-tide-500/[0.04] px-4 py-3 text-xs text-tide-300 transition-colors hover:bg-tide-500/[0.09]">
          <Send size={14} className="shrink-0" />
          <span className="flex-1 leading-relaxed text-slate-300">
            <b className="text-tide-300">完全透明</b>：每一筆信號均公開發佈於 Telegram 頻道，訂閱前可自行查閱完整歷史記錄。
          </span>
          <ArrowRight size={12} className="shrink-0 text-slate-500" />
        </a>
        <div className="mt-3 text-[10px] leading-relaxed text-slate-600">付款方式：NOWPayments（USDT / BTC / ETH）。本服務為策略參考，不構成投資建議。取消訂閱請聯絡客服。</div>
      </div>
    </div>
  );
}
