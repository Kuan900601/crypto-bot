"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Radio, BrainCircuit, Newspaper, Activity, FlaskConical, Waves } from "lucide-react";
const NAV = [
  { href: "/", label: "市場總覽", icon: LayoutDashboard },
  { href: "/signals", label: "黑潮船長", icon: Radio },
  { href: "/analysis", label: "AI 分析", icon: BrainCircuit },
  { href: "/news", label: "新聞中心", icon: Newspaper },
  { href: "/monitor", label: "異常監控", icon: Activity },
  { href: "/backtest", label: "策略回測", icon: FlaskConical },
];
export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const [logoOk, setLogoOk] = useState(true);
  return (
    <aside className="flex h-full w-60 flex-col border-r border-white/5 bg-ink-900/95">
      <div className="flex items-center gap-3 px-5 py-5">
        {logoOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src="/brand/logo.png" alt="黑潮 Signals"
            className="h-10 w-10 rounded-full object-cover ring-1 ring-tide-400/40 shadow-[0_0_18px_rgba(212,175,55,0.25)]"
            onError={() => setLogoOk(false)} />
        ) : (
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-tide-400 to-tide-600 text-ink-950">
            <Waves size={20} strokeWidth={2.5} />
          </div>
        )}
        <div>
          <div className="font-display text-sm font-bold tracking-widest text-gold">黑潮 BLACKTIDE</div>
          <div className="text-[9px] tracking-[0.2em] text-slate-500">SIGNALS · PRO TERMINAL</div>
        </div>
      </div>
      <div className="hairline-gold mx-4" />
      <nav className="mt-3 flex-1 space-y-1 px-3">
        {NAV.map((n) => {
          const active = pathname === n.href;
          const Icon = n.icon;
          return (
            <Link key={n.href} href={n.href} onClick={onNavigate}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${active ? "bg-tide-500/15 text-tide-300" : "text-slate-400 hover:bg-white/5 hover:text-slate-200"}`}>
              <Icon size={17} />
              {n.label}
              {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-tide-400 shadow-[0_0_8px_rgba(212,175,55,0.6)]" />}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-white/5 p-4 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span className="pulse-dot h-2 w-2 rounded-full bg-up" />
          行情：Bybit 即時
        </div>
        <div className="mt-1 text-[10px]">v0.3.0 · 訊號統計於黑潮船長頁</div>
      </div>
    </aside>
  );
}
