"use client";

import Link from "next/link";
import { Lock } from "lucide-react";
import { usePremium } from "@/lib/usePremium";

// 付費牆：非 premium 看到模糊內容 + 升級 CTA；premium/admin 直接看內容。
export default function Paywall({ children, blurb }: { children: React.ReactNode; blurb?: string }) {
  const { isPremium, loading } = usePremium();
  if (loading || isPremium) return <>{children}</>;

  return (
    <div className="relative overflow-hidden rounded-2xl">
      <div className="pointer-events-none select-none blur-sm" aria-hidden>
        {children}
      </div>
      <div className="absolute inset-0 grid place-items-center bg-ink-950/70 p-6 text-center">
        <div className="max-w-sm">
          <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full bg-tide-500/15 text-tide-300">
            <Lock size={20} />
          </div>
          <div className="text-sm font-semibold text-slate-100">Premium 專屬內容</div>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">
            {blurb || "升級 Premium 解鎖完整信號、進出場價位與分析。"}
          </p>
          <Link
            href="/pricing"
            className="mt-4 inline-block rounded-lg bg-tide-500 px-4 py-2 text-sm font-semibold text-ink-950 hover:bg-tide-400"
          >
            查看方案
          </Link>
        </div>
      </div>
    </div>
  );
}
