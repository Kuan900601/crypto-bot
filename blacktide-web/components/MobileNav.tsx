"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Radio, LineChart, Newspaper, Crown } from "lucide-react";

const ITEMS = [
  { href: "/", label: "總覽", icon: LayoutDashboard },
  { href: "/signals", label: "信號", icon: Radio },
  { href: "/analysis", label: "分析", icon: LineChart },
  { href: "/news", label: "情報", icon: Newspaper },
  { href: "/pricing", label: "方案", icon: Crown },
];

export default function MobileNav() {
  const pathname = usePathname();
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-tide-500/15 bg-ink-900/90 backdrop-blur-lg md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="grid grid-cols-5">
        {ITEMS.map((it) => {
          const active = it.href === "/" ? pathname === "/" : pathname.startsWith(it.href);
          const Icon = it.icon;
          return (
            <Link
              key={it.href}
              href={it.href}
              className={
                "flex flex-col items-center gap-0.5 py-2 text-[10px] transition-colors " +
                (active ? "text-tide-300" : "text-slate-500")
              }
            >
              <Icon size={18} />
              {it.label}
              <span className={"h-0.5 w-5 rounded-full " + (active ? "bg-tide-400" : "bg-transparent")} />
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
