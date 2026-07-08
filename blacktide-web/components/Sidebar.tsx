"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Radio, BrainCircuit, Newspaper, Activity, FlaskConical, Gift, UserCircle, BookOpen, Send, ArrowRight, HelpCircle, CalendarDays, LineChart } from "lucide-react";
import { requiredTier } from "@/lib/access";
import { C } from "@/lib/theme";
import LogoMark from "@/components/site/LogoMark";

const NAV_MAIN = [
  { href: "/", label: "市場總覽", icon: LayoutDashboard },
  { href: "/signals", label: "黑潮船長", icon: Radio },
  { href: "/analysis", label: "AI 分析", icon: BrainCircuit },
  { href: "/news", label: "新聞中心", icon: Newspaper },
  { href: "/calendar", label: "事件行事曆", icon: CalendarDays },
  { href: "/stocks", label: "美股分析", icon: LineChart },
  { href: "/monitor", label: "異常監控", icon: Activity },
  { href: "/backtest", label: "策略回測", icon: FlaskConical },
];
const NAV_ME = [
  { href: "/member", label: "會員中心", icon: UserCircle },
  { href: "/activity", label: "福利中心", icon: Gift },
  { href: "/guide", label: "使用教學", icon: BookOpen },
  { href: "/faq", label: "常見問題", icon: HelpCircle },
];

// 徽章一律照 lib/access.ts 的真實 requiredTier() 顯示，不自行改門檻或顯示成更高方案。
function TierTag({ href }: { href: string }) {
  const t = requiredTier(href);
  if (!t) return null;
  const pro = t === "pro";
  return (
    <span style={{
      marginLeft: "auto", fontSize: 9.5, fontWeight: 800, letterSpacing: 1, padding: "2px 8px", borderRadius: 7,
      color: pro ? C.abyss : C.primary,
      background: pro ? `linear-gradient(135deg,${C.primary},${C.primary2})` : "rgba(0,212,255,0.1)",
      border: pro ? "none" : `1px solid ${C.primary}40`,
    }}>
      {pro ? "PRO" : "PLUS"}
    </span>
  );
}

function NavLink({ href, label, Icon, active, onNavigate }: { href: string; label: string; Icon: typeof LayoutDashboard; active: boolean; onNavigate?: () => void }) {
  return (
    <Link href={href} onClick={onNavigate} className="mrow" style={{
      display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 11,
      background: active ? "linear-gradient(100deg, rgba(0,212,255,0.14), rgba(0,212,255,0.03))" : "transparent",
      border: active ? `1px solid ${C.primary}30` : "1px solid transparent",
      position: "relative", textDecoration: "none",
    }}>
      {active && <div style={{ position: "absolute", left: 0, top: "50%", transform: "translateY(-50%)", width: 3, height: 18, borderRadius: 3, background: `linear-gradient(${C.primary},${C.teal})` }} />}
      <Icon size={17} strokeWidth={1.8} color={active ? C.primary : C.mut} style={{ flexShrink: 0 }} />
      <span style={{ flex: 1, fontSize: 13.5, fontWeight: active ? 700 : 600, color: active ? C.ink : "#B9C7D2" }}>{label}</span>
      <TierTag href={href} />
    </Link>
  );
}

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <aside style={{
      display: "flex", flexDirection: "column", height: "100%", width: 240,
      borderRight: `1px solid ${C.line}`, background: "rgba(4,9,16,0.92)", backdropFilter: "blur(20px)",
      position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(360px 280px at 15% 0%, rgba(19,53,90,0.35), transparent 60%)", pointerEvents: "none" }} />
      {/* safe-area 頂部內距已由 Shell 根容器統一處理 */}
      <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 11, padding: "18px 18px 14px" }}>
        <LogoMark size={40} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 800, fontSize: 14, letterSpacing: "0.04em", color: C.ink, lineHeight: 1.15 }}>黑潮 BLACKTIDE</div>
          <div style={{ fontSize: 8.5, fontWeight: 600, letterSpacing: "0.28em", color: C.primary, marginTop: 2 }}>SIGNALS · PRO TERMINAL</div>
        </div>
      </div>
      <div style={{ height: 1, margin: "0 16px", background: `linear-gradient(90deg, transparent, ${C.linePrimary}, transparent)` }} />
      <nav style={{ position: "relative", marginTop: 10, flex: 1, overflowY: "auto", padding: "0 12px", display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV_MAIN.map((n) => <NavLink key={n.href} href={n.href} label={n.label} Icon={n.icon} active={pathname === n.href} onNavigate={onNavigate} />)}
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2, color: C.dim, margin: "16px 12px 6px" }}>其他</div>
        {NAV_ME.map((n) => <NavLink key={n.href} href={n.href} label={n.label} Icon={n.icon} active={pathname === n.href} onNavigate={onNavigate} />)}
      </nav>
      <div style={{ position: "relative", padding: "10px 12px" }}>
        <a href="https://t.me/KuroshioSignal" target="_blank" rel="noopener noreferrer" className="tg-btn"
          style={{ display: "flex", alignItems: "center", gap: 9, padding: "10px 12px", borderRadius: 11, background: "rgba(0,212,255,0.06)", border: `1px solid ${C.teal}33`, color: C.ink, textDecoration: "none", fontSize: 12.5, fontWeight: 700 }}>
          <Send size={14} color={C.teal} /><span style={{ flex: 1 }}>Telegram 社群頻道</span><ArrowRight size={13} color={C.teal} />
        </a>
      </div>
      <div style={{ position: "relative", borderTop: `1px solid ${C.line}`, padding: "10px 16px 12px", fontSize: 11, color: C.mut }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ width: 6, height: 6, borderRadius: 99, background: C.green, boxShadow: `0 0 6px ${C.green}`, animation: "pulseDot 1.6s infinite" }} />
          行情：Bybit 即時
        </div>
        <div style={{ fontSize: 10, color: C.dim, marginTop: 4 }}>© {new Date().getFullYear()} 黑潮 BLACKTIDE</div>
      </div>
    </aside>
  );
}
