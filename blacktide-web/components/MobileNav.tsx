"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Radio, BrainCircuit, Newspaper, Activity } from "lucide-react";
import { C } from "@/lib/theme";
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
    <nav className="fixed inset-x-0 bottom-0 z-40 backdrop-blur-xl md:hidden"
      style={{ background: "rgba(4,9,16,0.92)", borderTop: `1px solid ${C.lineGold}`, paddingBottom: "env(safe-area-inset-bottom)" }}>
      <div className="mx-auto grid max-w-md grid-cols-5">
        {ITEMS.map((it) => {
          const active = pathname === it.href;
          const Icon = it.icon;
          return (
            <Link key={it.href} href={it.href} className="flex flex-col items-center gap-1 py-2">
              <span className="flex h-7 w-12 items-center justify-center rounded-full" style={{
                background: active ? "rgba(232,198,110,0.14)" : "transparent",
                color: active ? C.gold : C.mut,
              }}><Icon size={18} /></span>
              <span style={{ fontSize: 10, color: active ? C.gold : C.mut }}>{it.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
