"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { motion } from "framer-motion";
import { Lock, Clock, LogIn } from "lucide-react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import MobileNav from "./MobileNav";
import PricingModal from "./PricingModal";
import Footer from "./Footer";
import { useApp } from "@/lib/store";
import { canAccess, requiredTier, TIER_LABEL, Tier } from "@/lib/access";
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
function GuestBanner() {
  return (
    <div className="mb-4 flex items-center gap-2 rounded-xl border border-tide-500/20 bg-tide-500/[0.06] px-4 py-2.5 text-xs text-tide-300">
      <LogIn size={14} className="shrink-0" />
      <span className="flex-1 text-slate-300">你正以訪客模式瀏覽 · <b className="text-tide-300">點擊任意功能即可登入使用</b></span>
      <Link href="/login" className="rounded-lg bg-tide-500/20 px-3 py-1 font-semibold hover:bg-tide-500/30">登入</Link>
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
  const unauth = !isPublic && status === "unauthenticated";
  const tierLocked = !isPublic && status === "authenticated" && !!req && !canAccess(pathname, tier);
  const handleGuestClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    router.push("/login?next=" + encodeURIComponent(pathname));
  };
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
        {/* PWA 安全區：iOS 狀態列補丁 */}
        <div className="shrink-0" style={{ height: "env(safe-area-inset-top, 0px)", background: "rgba(6,7,11,0.97)" }} />
        <Topbar onMenu={() => setOpen(true)} />
        <main
          className="relative flex-1 overflow-y-auto px-4 pb-24 pt-5 md:px-8 md:pb-8 md:pt-6"
          onClickCapture={unauth ? handleGuestClick : undefined}
        >
          {unauth && <GuestBanner />}
          {!unauth && status === "authenticated" && <ExpiryBanner />}
          <motion.div key={pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            {children}
          </motion.div>
          {!tierLocked && <Footer />}
          {tierLocked && (
            <div onClick={() => setPricingOpen(true)} className="absolute inset-0 z-20 flex cursor-pointer items-start justify-center bg-ink-950/60 pt-24 backdrop-blur-sm">
              <div onClick={(e) => e.stopPropagation()} className="mx-4 w-full max-w-sm rounded-2xl border border-tide-500/20 bg-ink-800 p-6 text-center">
                <Lock className="mx-auto text-tide-300" size={26} />
                <div className="mt-3 font-display text-sm font-bold text-gold">需要升級方案</div>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
                  此功能需要 {req ? TIER_LABEL[req] : "更高方案"}。你目前是 {TIER_LABEL[tier]}。
                </p>
                <div className="mt-4 flex gap-2">
                  <button onClick={() => setPricingOpen(true)} className="flex-1 rounded-lg bg-amber-500/15 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/25">查看方案</button>
                </div>
              </div>
            </div>
          )}
        </main>
        <MobileNav />
      </div>
      <PricingModal />
    </div>
  );
}
