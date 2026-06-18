"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Radio, BrainCircuit, Newspaper, Activity, FlaskConical, Gift, UserCircle, Waves, BookOpen, Send, ArrowRight, HelpCircle, CalendarDays, LineChart } from "lucide-react";
import { requiredTier } from "@/lib/access";
const NAV_MAIN = [
  { href: "/", label: "市場總覽", icon: LayoutDashboard },
  { href: "/signals", label: "黑潮船長", icon: Radio },
  { href: "/member", label: "會員中心", icon: UserCircle },
  { href: "/analysis", label: "AI 分析", icon: BrainCircuit },
  { href: "/news", label: "新聞中心", icon: Newspaper },
  { href: "/calendar", label: "事件行事曆", icon: CalendarDays },
  { href: "/stocks", label: "美股分析", icon: LineChart },
  { href: "/monitor", label: "異常監控", icon: Activity },
  { href: "/backtest", label: "策略回測", icon: FlaskConical },
];
const NAV_ME = [
  { href: "/activity", label: "福利中心", icon: Gift },
  { href: "/guide", label: "使用教學", icon: BookOpen },
  { href: "/faq", label: "常見問題", icon: HelpCircle },
];
function TierTag({ href }: { href: string }) {
  const t = requiredTier(href);
  if (!t) return null;
  const pro = t === "pro";
  return <span className={`ml-auto rounded-md px-1.5 py-0.5 text-[9px] font-bold tracking-wide ${pro ? "bg-amber-500/15 text-amber-300" : "bg-tide-500/15 text-tide-300"}`}>{pro ? "PRO" : "PLUS"}</span>;
}
function NavLink({ href, label, Icon, active, onNavigate }: { href: string; label: string; Icon: typeof LayoutDashboard; active: boolean; onNavigate?: () => void }) {
  return (
    <Link href={href} onClick={onNavigate}
      className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-150 ${active ? "bg-tide-500/15 text-tide-300" : "text-slate-400 hover:bg-white/5 hover:text-slate-200"}`}>
      <Icon size={17} className={active ? "text-tide-300" : ""} />
      <span>{label}</span>
      <TierTag href={href} />
    </Link>
  );
}
export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const [logoOk, setLogoOk] = useState(true);
  return (
    <aside className="flex h-full w-60 flex-col border-r border-white/5 bg-ink-900/80 backdrop-blur-xl">
      <div className="shrink-0" style={{ height: "env(safe-area-inset-top, 0px)" }} />
      <div className="flex items-center gap-3 px-5 py-5">
        {logoOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src="/brand/logo.png" alt="黑潮 Signals" className="h-10 w-10 rounded-full object-cover ring-1 ring-tide-400/40" onError={() => setLogoOk(false)} />
        ) : (
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-tide-400 to-tide-600 text-ink-950"><Waves size={20} strokeWidth={2.5} /></div>
        )}
        <div>
          <div className="font-display text-sm font-bold tracking-widest text-gold">黑潮 BLACKTIDE</div>
          <div className="text-[9px] tracking-[0.2em] text-slate-500">SIGNALS · PRO TERMINAL</div>
        </div>
      </div>
      <div className="hairline-gold mx-4" />
      <nav className="mt-3 flex-1 space-y-0.5 overflow-hidden px-3">
        {NAV_MAIN.map((n) => <NavLink key={n.href} href={n.href} label={n.label} Icon={n.icon} active={pathname === n.href} onNavigate={onNavigate} />)}
        <div className="px-3 pb-0.5 pt-3 text-[10px] font-semibold tracking-wider text-slate-600">其他</div>
        {NAV_ME.map((n) => <NavLink key={n.href} href={n.href} label={n.label} Icon={n.icon} active={pathname === n.href} onNavigate={onNavigate} />)}
      </nav>
      <div className="px-3 py-2">
        <a href="https://t.me/KuroshioSignal" target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-2 rounded-xl border border-tide-500/20 bg-tide-500/[0.06] px-3 py-2 text-xs text-tide-300 transition-colors hover:bg-tide-500/[0.12]">
          <Send size={13} />
          <span className="font-semibold">Telegram 社群頻道</span>
          <ArrowRight size={11} className="ml-auto" />
        </a>
      </div>
      <div className="border-t border-white/5 px-4 py-2.5 text-xs text-slate-500">
        <div className="flex items-center gap-2"><span className="pulse-dot h-2 w-2 rounded-full bg-up" /> 行情：Bybit 即時</div>
        <div className="mt-0.5 text-[10px]">© {new Date().getFullYear()} 黑潮 BLACKTIDE</div>
      </div>
    </aside>
  );
}
