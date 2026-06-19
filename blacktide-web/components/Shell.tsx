"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { motion } from "framer-motion";
import { Clock, Lock, Unlock } from "lucide-react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import MobileNav from "./MobileNav";
import PricingModal from "./PricingModal";
import Footer from "./Footer";
import Analytics from "./Analytics";
import VerifyBanner from "./VerifyBanner";
import { useApp } from "@/lib/store";
import { canAccess, requiredTier, Tier } from "@/lib/access";

function ExpiryBanner() {
  const { data: session } = useSession();
  const setPricingOpen = useApp((s) => s.setPricingOpen);
  const exp = session?.user?.planExpiry;
  if (!exp) return null;
  const days = Math.ceil((new Date(exp).getTime() - Date.now()) / 86400000);
  if (days < 0 || days > 7) return null;
  return (
    <div className="mb-4 flex items-center gap-2 rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-200">
      <Clock size={14} className="shrink-0" />
      <span>你的訂閱將在 <b>{days === 0 ? "今天" : days + " 天後"}</b> 到期。</span>
      <button onClick={() => setPricingOpen(true)} className="ml-auto rounded-lg bg-amber-500/20 px-3 py-1 font-semibold hover:bg-amber-500/30">續訂</button>
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { data: session, status } = useSession();
  const setPricingOpen = useApp((s) => s.setPricingOpen);
  const tier: Tier = (session?.user?.tier as Tier) || "free";
  const isPublic = pathname === "/login" || pathname.startsWith("/legal");
  const req = requiredTier(pathname);

  // Partial lock: applies when page requires a tier and user can't access
  const partialLocked = !isPublic && !!req && (
    status === "unauthenticated" ||
    (status === "authenticated" && !canAccess(pathname, tier))
  );

  // Tier upgrade lock (authenticated user with wrong tier, full page lock for UX)
  // Replaced by partialLocked for V13

  void setPricingOpen; // kept for pricing modal trigger in other pages

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="hidden h-full md:block"><Sidebar /></div>
      {open && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-60"><Sidebar onNavigate={() => setOpen(false)} /></div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* PWA 安全區 */}
        <div className="shrink-0" style={{ height: "env(safe-area-inset-top, 0px)", background: "rgba(6,7,11,0.97)" }} />
        <Topbar onMenu={() => setOpen(true)} />

        {/* Content wrapper — relative so lock overlay can be anchored here, NOT inside scroll */}
        <div className="relative flex-1 overflow-hidden">
          <main className={`h-full px-4 pb-24 pt-5 md:px-8 md:pb-8 md:pt-6 ${partialLocked ? "overflow-hidden" : "overflow-y-auto"}`}>
            {status === "authenticated" && <VerifyBanner />}
            {status === "authenticated" && <ExpiryBanner />}
            <motion.div key={pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
              {children}
            </motion.div>
            {!partialLocked && <Footer />}
          </main>

          {/* ── Partial lock overlay ──
              Positioned outside <main> so it does NOT scroll with content.
              Shows 30% of content; covers the bottom 70% with blur + gradient.
              <main> is overflow-hidden when partialLocked to prevent ANY scrolling. */}
          {partialLocked && (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 rounded-t-3xl overflow-hidden" style={{ top: "28%" }}>
              {/* gradient fade: transparent → frosted glass (短，毛玻璃盡快出現) */}
              <div className="absolute inset-x-0 top-0 h-10 bg-gradient-to-b from-transparent to-white/[0.01]" />
              {/* 毛玻璃遮罩 — 從 top-8 開始，確保蓋過解鎖按鈕 */}
              <div className="absolute inset-0 top-8 backdrop-blur-xl bg-white/[0.015]" />
              {/* clickable area — entire locked zone redirects to login */}
              <div
                className="pointer-events-auto absolute inset-0 flex flex-col items-center justify-start pt-16 cursor-pointer"
                onClick={() => router.push("/login?next=" + encodeURIComponent(pathname))}
              >
                <button
                  className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-tide-400 to-tide-600 px-6 py-3.5 text-sm font-bold text-ink-950 shadow-2xl shadow-tide-500/30 hover:opacity-90 active:scale-95"
                  onClick={(e) => { e.stopPropagation(); router.push("/login?next=" + encodeURIComponent(pathname)); }}
                >
                  <Unlock size={16} />
                  立即解鎖完整內容
                </button>
                <p className="mt-3 text-xs text-slate-400">免費註冊即可查看 · 訂閱解鎖全部功能</p>
                <div className="mt-4 flex gap-3">
                  <Link
                    href="/login"
                    onClick={(e) => e.stopPropagation()}
                    className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs text-slate-200 hover:bg-white/10"
                  >
                    登入
                  </Link>
                  <Link
                    href="/login?register=1"
                    onClick={(e) => e.stopPropagation()}
                    className="rounded-xl border border-tide-500/30 bg-tide-500/10 px-4 py-2 text-xs text-tide-300 hover:bg-tide-500/20"
                  >
                    免費註冊
                  </Link>
                </div>
              </div>
            </div>
          )}

          {/* Sidebar tier-lock (for authenticated users who need to upgrade) */}
          {!partialLocked && status === "authenticated" && !!req && !canAccess(pathname, tier) && (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 rounded-t-3xl overflow-hidden" style={{ top: "28%" }}>
              <div className="absolute inset-x-0 top-0 h-10 bg-gradient-to-b from-transparent to-white/[0.01]" />
              <div className="absolute inset-0 top-8 backdrop-blur-xl bg-white/[0.015]" />
              <div
                className="pointer-events-auto absolute inset-0 flex flex-col items-center justify-start pt-16 cursor-pointer"
                onClick={() => setPricingOpen(true)}
              >
                <button
                  className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-amber-400 to-amber-600 px-6 py-3.5 text-sm font-bold text-ink-950 shadow-2xl"
                  onClick={(e) => { e.stopPropagation(); setPricingOpen(true); }}
                >
                  <Lock size={16} />
                  升級解鎖
                </button>
                <p className="mt-3 text-xs text-slate-400">此頁需要更高方案</p>
              </div>
            </div>
          )}
        </div>

        <MobileNav />
      </div>
      <PricingModal />
      <Analytics />
    </div>
  );
}
