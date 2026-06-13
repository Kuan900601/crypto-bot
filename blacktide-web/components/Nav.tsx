"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Radio, LineChart, Newspaper, Activity, FlaskConical, Crown, User,
} from "lucide-react";
import { usePremium } from "@/lib/usePremium";

const LINKS = [
  { href: "/", label: "總覽", icon: LayoutDashboard },
  { href: "/signals", label: "信號", icon: Radio },
  { href: "/analysis", label: "分析", icon: LineChart },
  { href: "/news", label: "情報", icon: Newspaper },
  { href: "/monitor", label: "監控", icon: Activity },
  { href: "/backtest", label: "驗證", icon: FlaskConical },
  { href: "/pricing", label: "方案", icon: Crown },
];

export default function Nav() {
  const path = usePathname();
  const { authed, isPremium, isAdmin, user } = usePremium();

  return (
    <aside className="sticky top-0 z-20 flex h-screen w-[72px] flex-col items-center gap-1 border-r border-ink-700 bg-ink-900/80 py-4 backdrop-blur lg:w-56 lg:items-stretch lg:px-3">
      <Link href="/" className="mb-4 flex items-center gap-2 px-2 lg:px-1">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-tide-400 to-tide-600 font-bold text-ink-950">黑</div>
        <div className="hidden flex-col leading-tight lg:flex">
          <span className="text-sm font-semibold tracking-wide text-slate-100">黑潮 BLACKTIDE</span>
          <span className="text-[10px] text-slate-500">Signals Console</span>
        </div>
      </Link>
      <nav className="flex flex-1 flex-col gap-1">
        {LINKS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={
                "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition " +
                (active
                  ? "bg-tide-500/15 text-tide-300 ring-1 ring-tide-500/30"
                  : "text-slate-400 hover:bg-ink-700/60 hover:text-slate-200")
              }
            >
              <Icon size={18} className="shrink-0" />
              <span className="hidden lg:inline">{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* 帳號區 */}
      <Link
        href={authed ? "/account" : "/login"}
        className="mt-2 flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-400 hover:bg-ink-700/60 hover:text-slate-200"
      >
        <User size={18} className="shrink-0" />
        <span className="hidden min-w-0 flex-col lg:flex">
          {authed ? (
            <>
              <span className="truncate text-xs text-slate-200">{user?.name || user?.email}</span>
              <span className={"text-[10px] " + (isPremium ? "text-tide-300" : "text-slate-500")}>
                {isAdmin ? "Admin" : isPremium ? "Premium" : "Free"}
              </span>
            </>
          ) : (
            <span className="text-xs">登入 / 註冊</span>
          )}
        </span>
      </Link>
    </aside>
  );
}
