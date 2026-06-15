"use client";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Card, SectionTitle, Stat, Badge } from "@/components/ui";
interface AdminUser { email: string; name: string; phone: string; uid: string; tier: string; cycle?: string; subAmount?: number; createdAt: string; }
interface Feedback { id: string; email: string; name: string; phone: string; uid: string; tier: string; content: string; createdAt: string; }
interface Data { stats: { totalUsers: number; free: number; air: number; pro: number; mrr: number; recorded: number }; users: AdminUser[]; feedback: Feedback[]; }
const fmtTime = (s: string) => { try { return new Date(s).toLocaleString("zh-TW", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return s; } };
export default function AdminPage() {
  const { data: session, status } = useSession();
  const [data, setData] = useState<Data | null>(null);
  const [tab, setTab] = useState<"users" | "feedback">("users");
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    fetch("/api/admin").then(async (r) => { if (!r.ok) { setErr(((await r.json()).error) || "讀取失敗"); return; } setData(await r.json()); }).catch(() => setErr("讀取失敗"));
  }, []);
  useEffect(() => { if (status === "authenticated") load(); }, [status, load]);
  const setTier = async (email: string, tier: string, cycle: string) => {
    await fetch("/api/admin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, tier, cycle }) });
    load();
  };
  if (status === "loading") return <div className="mx-auto mt-10 max-w-4xl"><Card className="h-40 animate-pulse" /></div>;
  if (!session?.user?.isAdmin) {
    return <div className="mx-auto mt-[15vh] max-w-md text-center"><Card className="p-8"><div className="text-sm text-slate-400">此頁僅限管理員。</div></Card></div>;
  }
  const s = data?.stats;
  return (
    <div className="space-y-5">
      <SectionTitle title="管理後台" desc="網站數據 · 訂閱收益 · 用戶資料 · 意見反饋"
        right={<button onClick={load} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5">重新整理</button>} />
      {err && <div className="rounded-xl border border-down/20 bg-down/10 px-4 py-2.5 text-xs text-down">{err}</div>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Stat label="總註冊人數" value={String(s?.totalUsers ?? 0)} />
        <Stat label="免費會員" value={String(s?.free ?? 0)} />
        <Stat label="Air 訂閱" value={String(s?.air ?? 0)} tone="up" />
        <Stat label="Pro 訂閱" value={String(s?.pro ?? 0)} tone="up" />
        <Stat label="月經常收入" value={"$" + (s?.mrr ?? 0)} sub="MRR 估算" />
        <Stat label="已記錄收益" value={"$" + (s?.recorded ?? 0)} sub="本期訂閱合計" />
      </div>
      <div className="inline-flex rounded-lg bg-white/[0.04] p-1 text-xs font-semibold">
        {(["users", "feedback"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-md px-3 py-1.5 ${tab === t ? "bg-tide-500/15 text-tide-300" : "text-slate-400"}`}>
            {t === "users" ? "用戶資料（" + (data?.users.length ?? 0) + "）" : "意見反饋（" + (data?.feedback.length ?? 0) + "）"}
          </button>
        ))}
      </div>
      {tab === "users" && (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead className="border-b border-white/5 text-slate-500">
              <tr><th className="px-3 py-2">姓名 / UID</th><th className="px-3 py-2">聯絡</th><th className="px-3 py-2">方案</th><th className="px-3 py-2">註冊</th><th className="px-3 py-2">設定等級</th></tr>
            </thead>
            <tbody>
              {(data?.users || []).map((u) => (
                <tr key={u.email} className="border-b border-white/5 last:border-0">
                  <td className="px-3 py-2"><div className="font-medium text-slate-200">{u.name || "—"}</div><div className="font-mono text-[10px] text-slate-600">{u.uid}</div></td>
                  <td className="px-3 py-2"><div className="text-slate-300">{u.email}</div><div className="text-slate-600">{u.phone || "—"}</div></td>
                  <td className="px-3 py-2"><Badge tone={u.tier === "pro" ? "amber" : u.tier === "air" ? "tide" : "slate"}>{u.tier}</Badge></td>
                  <td className="px-3 py-2 text-slate-500">{fmtTime(u.createdAt)}</td>
                  <td className="px-3 py-2">
                    <select defaultValue={u.tier + ":" + (u.cycle || "monthly")} onChange={(e) => { const [t, c] = e.target.value.split(":"); setTier(u.email, t, c); }}
                      className="rounded-lg border border-white/10 bg-ink-900 px-2 py-1 text-xs outline-none">
                      <option value="free:monthly">免費</option>
                      <option value="air:monthly">Air · 月</option>
                      <option value="air:yearly">Air · 年</option>
                      <option value="pro:monthly">Pro · 月</option>
                      <option value="pro:yearly">Pro · 年</option>
                    </select>
                  </td>
                </tr>
              ))}
              {(!data?.users || data.users.length === 0) && <tr><td colSpan={5} className="px-3 py-8 text-center text-slate-600">尚無用戶</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
      {tab === "feedback" && (
        <div className="space-y-3">
          {(data?.feedback || []).map((f) => (
            <Card key={f.id} className="p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-semibold text-slate-200">{f.name || "—"}</span>
                <Badge tone={f.tier === "pro" ? "amber" : f.tier === "air" ? "tide" : "slate"}>{f.tier}</Badge>
                <span className="text-slate-500">{f.email}</span>
                <span className="text-slate-600">{f.phone}</span>
                <span className="font-mono text-[10px] text-slate-600">{f.uid}</span>
                <span className="ml-auto text-[10px] text-slate-600">{fmtTime(f.createdAt)}</span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{f.content}</p>
            </Card>
          ))}
          {(!data?.feedback || data.feedback.length === 0) && <Card className="p-8 text-center text-sm text-slate-600">尚無反饋</Card>}
        </div>
      )}
    </div>
  );
}
