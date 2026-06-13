"use client";
import { create } from "zustand";
export interface Notif { id: string; title: string; body: string; time: string; read: boolean; }
interface AppState {
  watchlist: string[]; toggleWatch: (s: string) => void;
  selectedSymbol: string; setSymbol: (s: string) => void;
  notifs: Notif[]; pushNotif: (n: Omit<Notif, "read">) => void; markAllRead: () => void;
  pricingOpen: boolean; setPricingOpen: (v: boolean) => void;
}
export const useApp = create<AppState>((set) => ({
  watchlist: ["BTC", "SOL", "ETH"],
  toggleWatch: (s) => set((st) => ({
    watchlist: st.watchlist.includes(s) ? st.watchlist.filter((x) => x !== s) : [...st.watchlist, s],
  })),
  selectedSymbol: "BTC",
  setSymbol: (s) => set({ selectedSymbol: s }),
  notifs: [
    { id: "seed-1", title: "新信號：SOL 做多", body: "Tier A · 進場 174.2–176.8 · 槓桿 3x", time: "32 分鐘前", read: false },
    { id: "seed-2", title: "TP1 觸發：SOL", body: "已達 184.7（1.5R），止損上移鎖利。", time: "1 小時前", read: false },
  ],
  pushNotif: (n) => set((st) => ({ notifs: [{ ...n, read: false }, ...st.notifs].slice(0, 30) })),
  markAllRead: () => set((st) => ({ notifs: st.notifs.map((n) => ({ ...n, read: true })) })),
  pricingOpen: false,
  setPricingOpen: (v) => set({ pricingOpen: v }),
}));
