"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Radio, BrainCircuit, Newspaper, Activity, FlaskConical, Waves } from "lucide-react";
import { requiredTier } from "@/lib/access";
const NAV = [
  { href: "/", label: "市場總覽", icon: LayoutDashboard },
  { href: "/signals", label: "黑潮船長", icon: Radio },
  { href: "/analysis", label: "AI 分析", icon: BrainCircuit },
  { href: "/news", label: "新聞中心", icon: Newspaper },
  { href: "/monitor", label: "異常監控", icon: Activity },
  { href: "/backtest", label: "策略回測", icon: FlaskConical },
];
const LEGAL = [
  { href: "/legal/terms", label: "服務條款" },
  { href: "/legal/disclaimer", label: "免責聲明" },
  { href: "/legal/privacy", label: "隱私權政策" },
  { href: "/legal/risk", label: "風險揭露聲明" },
];
function TierTag({ href }: { href: string }) {
  const t = requiredTier(href);
  if (!t) return null;
  const pro = t === "pro";
  return <span className={`ml-auto rounded-md px-1.5 py-0.5 text-[9px] font-bold tracking-wide ${pro ? "bg-amber-500/15 text-amber-300" : "bg-tide-500/15 text-tide-300"}`}>{pro ? "PRO" : "AIR"}</span>;
}
export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const [logoOk, setLogoOk] = useState(true);
  return (
    <aside className="flex h-full w-60 flex-col border-r border-white/5 bg-ink-900/80 backdrop-blur-xl">
      <div className="flex items-center gap-3 px-5 py-5">
        {logoOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src="/brand/logo.png" alt="黑潮 Signals" className="h-10 w-10 rounded-2xl object-cover ring-1 ring-tide-400/40" onError={() => setLogoOk(false)} />
        ) : (
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-tide-400 to-tide-600 text-ink-950"><Waves size={20} strokeWidth={2.5} /></div>
        )}
        <div>
          <div className="font-display text-sm font-bold tracking-widest text-gold">黑潮 BLACKTIDE</div>
          <div className="text-[9px] tracking-[0.2em] text-slate-500">SIGNALS · PRO TERMINAL</div>
        </div>
      </div>
      <div className="hairline-gold mx-4" />
      <nav className="mt-3 flex-1 space-y-1 overflow-y-auto px-3 scrollbar-none">
        {NAV.map((n) => {
          const active = pathname === n.href;
          const Icon = n.icon;
          return (
            <Link key={n.href} href={n.href} onClick={onNavigate}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all ${active ? "bg-tide-500/15 text-tide-300" : "text-slate-400 hover:bg-white/5 hover:text-slate-200"}`}>
              <Icon size={17} className={active ? "text-tide-300" : ""} />
              <span>{n.label}</span>
              <TierTag href={n.href} />
            </Link>
          );
        })}
      </nav>
      <div className="px-4 pb-2 pt-3">
        <div className="mb-1.5 text-[10px] font-semibold tracking-wider text-slate-600">法律聲明</div>
        <div className="flex flex-col gap-1">
          {LEGAL.map((l) => (
            <Link key={l.href} href={l.href} onClick={onNavigate} className="text-[11px] text-slate-500 hover:text-tide-300">{l.label}</Link>
          ))}
        </div>
      </div>
      <div className="border-t border-white/5 p-4 text-xs text-slate-500">
        <div className="flex items-center gap-2"><span className="pulse-dot h-2 w-2 rounded-full bg-up" /> 行情：Bybit 即時</div>
        <div className="mt-1 text-[10px]">© {new Date().getFullYear()} 黑潮 BLACKTIDE</div>
      </div>
    </aside>
  );
}
