"use client";
import { useState } from "react";
import Link from "next/link";
import { useSession, signOut } from "next-auth/react";
import { useApp } from "@/lib/store";
import { Crown, LogOut } from "lucide-react";
export default function UserMenu() {
  const { data: session, status } = useSession();
  const [open, setOpen] = useState(false);
  const setPricingOpen = useApp((s) => s.setPricingOpen);
  if (status === "loading") return <div className="h-8 w-8 animate-pulse rounded-full bg-white/10" />;
  if (!session?.user) {
    return <Link href="/login" className="rounded-lg bg-tide-500/15 px-3 py-1.5 text-xs font-semibold text-tide-300 hover:bg-tide-500/25">登入</Link>;
  }
  const u = session.user;
  const premium = u.isLifetime || u.plan === "premium";
  const planLabel = u.isLifetime ? "Lifetime Premium" : u.plan === "premium" ? "Premium" : "Free";
  return (
    <div className="relative">
      <button onClick={() => setOpen((v) => !v)} aria-label="使用者中心"
        className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-tide-400 to-amber-700 text-xs font-bold text-ink-950">
        {(u.name || u.email || "?").slice(0, 1).toUpperCase()}
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-40 w-72 rounded-xl border border-white/10 bg-ink-800 p-4 shadow-2xl">
          <div className="text-sm font-semibold">{u.name}</div>
          <div className="mt-0.5 font-mono text-[11px] text-slate-500">UID {u.uid}</div>
          <div className="text-[11px] text-slate-500">{u.email}</div>
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-white/[0.04] px-3 py-2 text-xs">
            <Crown size={14} className={premium ? "text-amber-300" : "text-slate-600"} />
            <span>{planLabel}</span>
            {u.isLifetime
              ? <span className="ml-auto text-amber-300/80">無到期日</span>
              : u.planExpiry ? <span className="ml-auto text-slate-500">到期 {u.planExpiry.slice(0, 10)}</span> : null}
          </div>
          {!premium && (
            <button onClick={() => { setOpen(false); setPricingOpen(true); }}
              className="mt-2 w-full rounded-lg bg-amber-500/15 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/25">
              升級會員
            </button>
          )}
          <button onClick={() => signOut({ callbackUrl: "/" })}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-white/10 py-2 text-xs text-slate-300 hover:bg-white/5">
            <LogOut size={13} />登出
          </button>
        </div>
      )}
    </div>
  );
}
