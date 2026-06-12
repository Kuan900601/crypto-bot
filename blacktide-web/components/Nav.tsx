"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Radio, LineChart, Newspaper, Activity, FlaskConical,
} from "lucide-react";

const LINKS = [
  { href: "/", label: "總覽", icon: LayoutDashboard },
  { href: "/signals", label: "信號", icon: Radio },
  { href: "/analysis", label: "分析", icon: LineChart },
  { href: "/news", label: "情報", icon: Newspaper },
  { href: "/monitor", label: "監控", icon: Activity },
  { href: "/backtest", label: "驗證", icon: FlaskConical },
];

export default function Nav() {
  const path = usePathname();
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
      <div className="hidden px-3 text-[10px] leading-relaxed text-slate-600 lg:block">
        驗證期 · SIM 模擬數據<br />v0.1
      </div>
    </aside>
  );
}
