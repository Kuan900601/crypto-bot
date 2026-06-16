"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Radio, BrainCircuit, Newspaper, Activity } from "lucide-react";
const ITEMS = [
  { href: "/", label: "總覽", icon: LayoutDashboard },
  { href: "/signals", label: "船長", icon: Radio },
  { href: "/analysis", label: "分析", icon: BrainCircuit },
  { href: "/news", label: "新聞", icon: Newspaper },
  { href: "/monitor", label: "監控", icon: Activity },
];
export default function MobileNav() {
  const pathname = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-white/5 bg-ink-900/70 backdrop-blur-xl md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <div className="mx-auto grid max-w-md grid-cols-5">
        {ITEMS.map((it) => {
          const active = pathname === it.href;
          const Icon = it.icon;
          return (
            <Link key={it.href} href={it.href} className="flex flex-col items-center gap-1 py-2">
              <span className={`flex h-7 w-12 items-center justify-center rounded-full transition-colors ${active ? "bg-tide-500/15 text-tide-300" : "text-slate-500"}`}><Icon size={18} /></span>
              <span className={`text-[10px] transition-colors ${active ? "text-tide-300" : "text-slate-500"}`}>{it.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
