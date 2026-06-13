"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";
import { usePremium } from "@/lib/usePremium";
import PageHeader from "@/components/PageHeader";

const FREE = ["即時行情與 K 線圖", "市場情報（情緒/熱度）", "總覽統計（勝率、期望值）"];
const PRO = [
  "完整追蹤中信號（方向/進場/止損/TP）",
  "歷史信號全紀錄",
  "多幣種分析與操作建議",
  "新信號即時通知",
];

export default function PricingPage() {
  const router = useRouter();
  const { authed, isPremium } = usePremium();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function subscribe() {
    setErr(null);
    if (!authed) { router.push("/login"); return; }
    setBusy(true);
    try {
      const r = await fetch("/api/checkout", { method: "POST" });
      const j = await r.json();
      if (!r.ok || !j.url) {
        const map: Record<string, string> = {
          NO_GATEWAY: "金流尚未設定（NOWPAYMENTS_API_KEY）",
          UNAUTH: "請先登入",
        };
        throw new Error(map[j.error] || j.error || "建立付款失敗");
      }
      window.location.href = j.url;
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="方案 Pricing"
        subtitle="以加密貨幣付款（NOWPayments）。Premium 解鎖完整信號與分析"
      />
      <div className="mx-auto grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-2">
        <div className="card p-5">
          <div className="text-sm font-semibold text-slate-300">Free</div>
          <div className="mt-1 text-2xl font-bold text-slate-100">$0</div>
          <ul className="mt-4 space-y-2 text-sm text-slate-400">
            {FREE.map((f) => (
              <li key={f} className="flex gap-2"><Check size={16} className="mt-0.5 shrink-0 text-slate-500" />{f}</li>
            ))}
          </ul>
        </div>

        <div className="card border border-tide-500/40 p-5 ring-1 ring-tide-500/20">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-tide-300">Premium</div>
            <span className="rounded-full bg-tide-500/15 px-2 py-0.5 text-[10px] text-tide-300">30 天</span>
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-100">
            ${process.env.NEXT_PUBLIC_PREMIUM_PRICE || "29"}
            <span className="text-sm font-normal text-slate-500"> / 月</span>
          </div>
          <ul className="mt-4 space-y-2 text-sm text-slate-300">
            {PRO.map((f) => (
              <li key={f} className="flex gap-2"><Check size={16} className="mt-0.5 shrink-0 text-tide-400" />{f}</li>
            ))}
          </ul>
          {isPremium ? (
            <div className="mt-5 rounded-lg bg-up/10 px-4 py-2 text-center text-sm text-up">已是 Premium 會員 ✓</div>
          ) : (
            <button
              onClick={subscribe}
              disabled={busy}
              className="mt-5 w-full rounded-lg bg-tide-500 px-4 py-2 text-sm font-semibold text-ink-950 hover:bg-tide-400 disabled:opacity-50"
            >
              {busy ? "前往付款…" : authed ? "用加密貨幣訂閱" : "登入後訂閱"}
            </button>
          )}
          {err && <div className="mt-2 text-xs text-down">{err}</div>}
        </div>
      </div>

      <p className="mx-auto mt-6 max-w-3xl text-center text-[11px] leading-relaxed text-slate-600">
        本服務提供之信號為策略驗證期之模擬數據，僅供研究參考，不構成投資建議，亦不保證獲利。投資有風險，請自負盈虧。
      </p>
    </div>
  );
}
