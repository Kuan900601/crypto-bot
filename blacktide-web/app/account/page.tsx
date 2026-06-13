"use client";

import { signOut } from "next-auth/react";
import Link from "next/link";
import { usePremium } from "@/lib/usePremium";
import PageHeader from "@/components/PageHeader";

export default function AccountPage() {
  const { loading, authed, isPremium, isAdmin, user } = usePremium();

  if (loading) return <div className="py-10 text-sm text-slate-500">讀取中…</div>;
  if (!authed) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-slate-400">尚未登入</p>
        <Link href="/login" className="mt-3 inline-block rounded-lg bg-tide-500 px-4 py-2 text-sm font-semibold text-ink-950">前往登入</Link>
      </div>
    );
  }

  const expiry = user?.planExpiry ? new Date(user.planExpiry).toLocaleDateString("zh-TW") : null;

  return (
    <div className="mx-auto max-w-lg">
      <PageHeader title="我的帳號 Account" subtitle="會員狀態與訂閱資訊" />
      <div className="card space-y-4 p-5">
        <Row label="Email" value={user?.email || "-"} />
        <Row label="暱稱" value={user?.name || "-"} />
        <Row
          label="方案"
          value={
            <span className={isPremium ? "text-tide-300" : "text-slate-400"}>
              {isAdmin ? "Admin（永久）" : isPremium ? "Premium" : "Free"}
            </span>
          }
        />
        {isPremium && !isAdmin && expiry && <Row label="到期日" value={expiry} />}

        <div className="flex gap-2 pt-2">
          {!isPremium && (
            <Link href="/pricing" className="flex-1 rounded-lg bg-tide-500 px-4 py-2 text-center text-sm font-semibold text-ink-950 hover:bg-tide-400">
              升級 Premium
            </Link>
          )}
          <button
            onClick={() => signOut({ callbackUrl: "/" })}
            className="flex-1 rounded-lg border border-ink-600 bg-ink-800 px-4 py-2 text-sm text-slate-300 hover:bg-ink-700"
          >
            登出
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-ink-700 pb-3 last:border-0 last:pb-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="font-mono text-sm text-slate-200">{value}</span>
    </div>
  );
}
