"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { motion } from "framer-motion";
import { Lock } from "lucide-react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import MobileNav from "./MobileNav";
import PricingModal from "./PricingModal";
import { useApp } from "@/lib/store";
export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { status } = useSession();
  const setPricingOpen = useApp((s) => s.setPricingOpen);
  const isPublic = pathname === "/" || pathname === "/login";
  const locked = !isPublic && status === "unauthenticated";
  return (
    <div className="flex h-screen overflow-hidden">
      <div className="hidden h-full md:block"><Sidebar /></div>
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="relative flex-1 overflow-y-auto px-3 pb-24 pt-4 md:px-6 md:pb-6 md:pt-5">
          <motion.div key={pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            {children}
          </motion.div>
          {locked && (
            <div onClick={() => setPricingOpen(true)}
              className="absolute inset-0 z-20 flex cursor-pointer items-start justify-center bg-ink-950/60 pt-24 backdrop-blur-sm">
              <div onClick={(e) => e.stopPropagation()}
                className="mx-4 w-full max-w-sm rounded-2xl border border-tide-500/20 bg-ink-800 p-6 text-center">
                <Lock className="mx-auto text-tide-300" size={26} />
                <div className="mt-3 font-display text-sm font-bold text-gold">會員專屬內容</div>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
                  登入後即可瀏覽完整內容；訂閱會員解鎖黑潮船長即時訊號與全部進階功能。
                </p>
                <div className="mt-4 flex gap-2">
                  <Link href="/login" className="flex-1 rounded-lg bg-tide-500/15 py-2 text-xs font-semibold text-tide-300 hover:bg-tide-500/25">登入</Link>
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
