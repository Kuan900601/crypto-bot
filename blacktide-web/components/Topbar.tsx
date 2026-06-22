"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { Search, Bell, X, Menu } from "lucide-react";
import { useApp } from "@/lib/store";
import { SymbolLite } from "@/lib/types";
import { C } from "@/lib/theme";
import LogoMark from "@/components/site/LogoMark";
import UserMenu from "./UserMenu";
import SymbolDetail from "./SymbolDetail";
export default function Topbar({ onMenu }: { onMenu?: () => void }) {
  const { status } = useSession();
  const { notifs, markAllRead, setDetail } = useApp();
  const unread = notifs.filter((n) => !n.read).length;
  const [q, setQ] = useState("");
  const [all, setAll] = useState<SymbolLite[]>([]);
  const [open, setOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (all.length || !open) return;
    fetch("/api/symbols").then((r) => r.json()).then((d) => setAll(d.symbols || [])).catch(() => {});
  }, [open, all.length]);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const ql = q.trim().toUpperCase();
  const results = ql ? all.filter((s) => s.symbol.toUpperCase().includes(ql) || s.name.toUpperCase().includes(ql)).slice(0, 30) : [];
  const pick = (s: SymbolLite) => { setDetail(s); setQ(""); setOpen(false); };
  return (
    <>
      <header className="sticky top-0 z-40 backdrop-blur" style={{ background: "rgba(4,9,16,0.86)", borderBottom: `1px solid ${C.lineGold}` }}>
        <div className="flex h-14 items-center gap-3 px-4">
          <div className="flex items-center gap-2 md:hidden">
            <button onClick={onMenu} aria-label="選單" className="ham rounded-lg p-1.5" style={{ color: C.gold, border: `1px solid ${C.line}` }}><Menu size={19} /></button>
            <LogoMark size={30} />
          </div>
          <div ref={boxRef} className="relative ml-1 min-w-0 flex-1 md:ml-0 md:max-w-md">
            <div className="flex items-center gap-2 rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2">
              <Search size={15} className="text-slate-500" />
              <input value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
                placeholder="搜尋幣種 / 美股（BTC、SOL、NVDA…）"
                className="w-full bg-transparent text-sm outline-none placeholder:text-slate-600" />
              {q && <button onClick={() => setQ("")} className="text-slate-500 hover:text-slate-300"><X size={14} /></button>}
            </div>
            {open && (ql ? results.length > 0 : all.length > 0) && (
              <div className="absolute left-0 right-0 top-12 z-50 max-h-80 overflow-y-auto rounded-xl border border-white/10 bg-ink-800 p-1.5 shadow-2xl">
                {(ql ? results : all.slice(0, 12)).map((s) => (
                  <button key={s.type + s.symbol + s.tvSymbol} onClick={() => pick(s)}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-white/5">
                    <span className="font-mono text-sm font-semibold">{s.symbol}</span>
                    <span className="truncate text-xs text-slate-500">{s.name}</span>
                    <span className={`ml-auto rounded px-1.5 py-0.5 text-[10px] ${s.type === "crypto" ? "bg-tide-500/15 text-tide-300" : "bg-amber-500/15 text-amber-300"}`}>{s.type === "crypto" ? "幣" : "股"}</span>
                  </button>
                ))}
                {!ql && <div className="px-3 py-1.5 text-[10px] text-slate-600">輸入代號搜尋 · 點選看即時圖表</div>}
              </div>
            )}
          </div>
          <div className="relative">
            <button onClick={() => { setBellOpen((v) => !v); if (!bellOpen) markAllRead(); }} className="relative rounded-lg p-2 text-slate-400 hover:bg-white/5">
              <Bell size={18} />
              {unread > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-tide-500" />}
            </button>
            {bellOpen && (
              <div className="absolute right-0 top-12 z-50 max-h-96 w-80 overflow-y-auto rounded-xl border border-white/10 bg-ink-800 p-1.5 shadow-2xl">
                <div className="px-2 py-1 text-xs font-semibold text-slate-400">通知</div>
                {notifs.length === 0 && <div className="px-2 py-3 text-xs text-slate-600">暫無通知</div>}
                {notifs.map((n) => (
                  <div key={n.id} className="rounded-lg px-2 py-2 hover:bg-white/5">
                    <div className="text-sm font-medium">{n.title}</div>
                    <div className="mt-0.5 text-xs text-slate-500">{n.body}</div>
                    <div className="mt-0.5 text-[10px] text-slate-600">{n.time}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          {status !== "authenticated" && (
            <Link href="/login?register=1" className="cta shrink-0 whitespace-nowrap" style={{
              borderRadius: 9, padding: "7px 14px", fontSize: 12.5, fontWeight: 800, color: C.abyss,
              background: `linear-gradient(135deg,#FFF4D2,${C.gold} 45%,${C.gold2})`,
            }}>
              免費註冊
            </Link>
          )}
          <UserMenu />
        </div>
      </header>
      <SymbolDetail />
    </>
  );
}
