"use client";

import { useSession } from "next-auth/react";

// 前端讀會員狀態。plan 由 NextAuth session callback 從 Redis 即時帶出（付款後不需重登）。
export function usePremium() {
  const { data, status } = useSession();
  return {
    loading: status === "loading",
    authed: status === "authenticated",
    isPremium: data?.user?.plan === "premium",
    isAdmin: !!data?.user?.isAdmin,
    user: data?.user,
  };
}
