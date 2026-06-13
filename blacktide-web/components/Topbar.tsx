"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, Search, Menu } from "lucide-react";
import { TICKERS } from "@/lib/mock";
import { useApp } from "@/lib/store";
import UserMenu from "./UserMenu";
export default function Topbar({ onMenu }: { onMenu: () => void }) {
  const [q, setQ] = useState("");
  const [showBell, setShowBell] = useState(false);
  const router = useRouter();
  const { setSymbol, notifs, markAllRead } = useApp();
  const unread = notifs.filter((n) => !n.read).length;
  const kw = q.trim().toLowerCase();
  const matches = kw ? TICKERS.filter((t) => (t.symbol + t.name).toLowerCase().includes(kw)).slice(0, 6) : [];
  return (
    <header className="relative z-30 flex h-14 shrink-0 items-center gap-3 border-b border-white/5 bg-ink-900/70 px-4 backdrop-blur">
      <button className="text-slate-400 md:hidden" onClick={onMenu} aria-label="選單"><Menu size={20} /></button>
      <div className="relative w-full max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜尋幣種 / 美股…"
          className="w-full rounded-lg border border-white/5 bg-ink-800 py-1.5 pl-9 pr-3 text-sm outline-none focus:border-tide-500/40" />
        {matches.length > 0 && (
          <div className="absolute top-10 z-40 w-full overflow-hidden rounded-lg border border-white/10 bg-ink-800 shadow-xl">
            {matches.map((t) => (
              <button key={t.symbol} onClick={() => { setSymbol(t.symbol); setQ(""); router.push("/"); }}
                className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-white/5">
                <span className="font-medium">{t.symbol}</span>
                <span className="text-xs text-slate-500">{t.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <div className="relative">
          <button onClick={() => setShowBell((v) => !v)} className="relative rounded-lg p-2 text-slate-400 hover:bg-white/5">
            <Bell size={18} />
            {unread > 0 && (
              <span className="absolute right-0.5 top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-tide-500 px-1 text-[9px] font-bold text-ink-950">{unread}</span>
            )}
          </button>
          {showBell && (
            <div className="absolute right-0 top-11 z-40 w-80 overflow-hidden rounded-xl border border-white/10 bg-ink-800 shadow-xl">
              <div className="flex items-center justify-between border-b border-white/5 px-4 py-2.5">
                <span className="text-sm font-semibold">通知</span>
                <button onClick={markAllRead} className="text-xs text-tide-400 hover:underline">全部已讀</button>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {notifs.length === 0 && <div className="p-4 text-sm text-slate-500">目前沒有通知</div>}
                {notifs.map((n) => (
                  <div key={n.id} className="border-b border-white/5 px-4 py-3 last:border-0">
                    <div className="flex items-center gap-2 text-sm">
                      {!n.read && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-tide-400" />}
                      <span className="font-medium">{n.title}</span>
                      <span className="ml-auto shrink-0 text-[10px] text-slate-500">{n.time}</span>
                    </div>
                    <div className="mt-0.5 text-xs text-slate-400">{n.body}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <UserMenu />
      </div>
    </header>
  );
}
