"use client";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Card, SectionTitle, Stat, Badge } from "@/components/ui";
import SignalPerf from "@/components/SignalPerf";
import { BadgeCheck, Eye, Clock } from "lucide-react";
interface AnalyticsData { totalPV: number; todayPV: number; yesterdayPV: number; avgSessionSec: number; sampleCount: number; pvByDay: { date: string; count: number }[]; }
interface AdminUser { email: string; nickname?: string; name: string; phone: string; uid: string; tier: string; cycle?: string; subAmount?: number; planExpiry?: string; emailVerified?: boolean; referrals: number; invitedBy?: string; referralRewarded?: number; createdAt: string; }
const tierUpper = (t: string) => (t === "air" ? "PLUS" : (t || "free").toUpperCase());
interface Feedback { id: string; email: string; name: string; phone: string; uid: string; tier: string; content: string; createdAt: string; }
interface Payment { id: string; email: string; tier: string; cycle: string; amount: number; payAmount?: number | null; payCurrency?: string | null; status: string; createdAt: string; }
interface Stats { totalUsers: number; free: number; air: number; pro: number; mrr: number; recorded: number; signups7d: number; byDay: { date: string; count: number }[]; revenuePaid: number; conversion: number; arpu: number; referralsTotal: number; rewardsTotal: number; }
interface Data { stats: Stats; users: AdminUser[]; feedback: Feedback[]; payments: Payment[]; }
const fmtTime = (s: string) => { try { return new Date(s).toLocaleString("zh-TW", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return s; } };
const fmtDuration = (sec: number) => { if (!sec) return "—"; if (sec < 60) return sec + " 秒"; return Math.floor(sec / 60) + " 分 " + (sec % 60) + " 秒"; };
const payTone = (s: string): "up" | "down" | "amber" | "slate" => s === "finished" ? "up" : (s === "failed" || s === "expired") ? "down" : "amber";
export default function AdminPage() {
  const { data: session, status } = useSession();
  const [data, setData] = useState<Data | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [tab, setTab] = useState<"users" | "activity" | "traffic" | "payments" | "feedback">("users");
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    fetch("/api/admin").then(async (r) => { if (!r.ok) { setErr(((await r.json()).error) || "讀取失敗"); return; } setData(await r.json()); }).catch(() => setErr("讀取失敗"));
    fetch("/api/analytics").then((r) => r.json()).then(setAnalytics).catch(() => {});
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
  const maxDay = Math.max(1, ...((s?.byDay || []).map((d) => d.count)));
  const maxPV = Math.max(1, ...((analytics?.pvByDay || []).map((d) => d.count)));
  return (
    <div className="space-y-5">
      <SectionTitle title="管理後台" desc="網站數據 · 訂閱收益 · 用戶資料 · 付款紀錄 · 意見反饋"
        right={<button onClick={load} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5">重新整理</button>} />
      {err && <div className="rounded-xl border border-down/20 bg-down/10 px-4 py-2.5 text-xs text-down">{err}</div>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="總註冊" value={String(s?.totalUsers ?? 0)} sub={"近7日 +" + (s?.signups7d ?? 0)} />
        <Stat label="免費 / Plus / Pro" value={(s?.free ?? 0) + " / " + (s?.air ?? 0) + " / " + (s?.pro ?? 0)} />
        <Stat label="付費轉換率" value={(s?.conversion ?? 0) + "%"} tone="up" />
        <Stat label="月經常收入" value={"$" + (s?.mrr ?? 0)} sub="MRR 估算" />
        <Stat label="ARPU" value={"$" + (s?.arpu ?? 0)} sub="每付費用戶平均" />
        <Stat label="本期記錄收益" value={"$" + (s?.recorded ?? 0)} sub="依現有訂閱" />
        <Stat label="實際已收款" value={"$" + (s?.revenuePaid ?? 0)} tone="up" sub="NOWPayments 完成" />
        <Stat label="Plus 訂閱數" value={String(s?.air ?? 0)} />
        <Stat label="Pro 訂閱數" value={String(s?.pro ?? 0)} />
        <Stat label="付款筆數" value={String(data?.payments.length ?? 0)} />
      </div>
      {/* 流量統計 */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-xl border border-white/5 bg-ink-800/60 p-4">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500"><Eye size={12} /> 總瀏覽次數</div>
          <div className="mt-1.5 font-display text-2xl font-bold">{(analytics?.totalPV ?? 0).toLocaleString()}</div>
          <div className="mt-0.5 text-[11px] text-slate-500">今日 {analytics?.todayPV ?? 0} · 昨日 {analytics?.yesterdayPV ?? 0}</div>
        </div>
        <div className="rounded-xl border border-white/5 bg-ink-800/60 p-4">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500"><Clock size={12} /> 平均停留時長</div>
          <div className="mt-1.5 font-display text-2xl font-bold">{fmtDuration(analytics?.avgSessionSec ?? 0)}</div>
          <div className="mt-0.5 text-[11px] text-slate-500">樣本 {(analytics?.sampleCount ?? 0).toLocaleString()} 筆</div>
        </div>
        <div className="rounded-xl border border-white/5 bg-ink-800/60 p-4">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">今日 PV</div>
          <div className="mt-1.5 font-display text-2xl font-bold text-tide-300">{analytics?.todayPV ?? 0}</div>
          <div className="mt-0.5 text-[11px] text-slate-500">昨日對比 {analytics?.yesterdayPV ? (analytics.todayPV >= analytics.yesterdayPV ? "+" : "") + ((analytics.todayPV - analytics.yesterdayPV) / Math.max(1, analytics.yesterdayPV) * 100).toFixed(0) + "%" : "—"}</div>
        </div>
        <div className="rounded-xl border border-white/5 bg-ink-800/60 p-4">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">PV / 用戶比</div>
          <div className="mt-1.5 font-display text-2xl font-bold">{s?.totalUsers ? ((analytics?.totalPV ?? 0) / s.totalUsers).toFixed(1) : "—"}</div>
          <div className="mt-0.5 text-[11px] text-slate-500">每位用戶平均頁面瀏覽</div>
        </div>
      </div>

      <SignalPerf />

      <Card className="p-4">
        <div className="mb-3 text-sm font-semibold">近 14 日註冊趨勢</div>
        <div className="flex h-28 items-end gap-1">
          {(s?.byDay || []).map((d, i) => (
            <div key={i} className="flex flex-1 flex-col items-center gap-1" title={d.date + "：" + d.count}>
              <div className="w-full rounded-t bg-tide-500/45" style={{ height: ((d.count / maxDay) * 92 + 2) + "px" }} />
              <span className="text-[8px] text-slate-600">{d.date.slice(3)}</span>
            </div>
          ))}
        </div>
      </Card>
      <div className="inline-flex rounded-lg bg-white/[0.04] p-1 text-xs font-semibold">
        {(["users", "activity", "traffic", "payments", "feedback"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-md px-3 py-1.5 transition-colors ${tab === t ? "bg-tide-500/15 text-tide-300" : "text-slate-400"}`}>
            {t === "users" ? "用戶（" + (data?.users.length ?? 0) + "）" : t === "activity" ? "活動" : t === "traffic" ? "流量" : t === "payments" ? "付款（" + (data?.payments.length ?? 0) + "）" : "反饋（" + (data?.feedback.length ?? 0) + "）"}
          </button>
        ))}
      </div>
      {tab === "traffic" && (
        <div className="space-y-4">
          {/* 14-day PV bar chart */}
          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold">近 14 日瀏覽次數（PV）</span>
              <span className="text-xs text-slate-500">總計 {(analytics?.totalPV ?? 0).toLocaleString()} 次</span>
            </div>
            <div className="flex h-28 items-end gap-1">
              {(analytics?.pvByDay || []).map((d, i) => (
                <div key={i} className="flex flex-1 flex-col items-center gap-1" title={d.date + "：" + d.count + " PV"}>
                  <div className="w-full rounded-t bg-blue-500/45" style={{ height: ((d.count / maxPV) * 92 + 2) + "px" }} />
                  <span className="text-[8px] text-slate-600">{d.date.slice(3)}</span>
                </div>
              ))}
            </div>
          </Card>
          {/* Session stats */}
          <Card className="p-4">
            <div className="mb-3 text-sm font-semibold">使用時長分析</div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-center">
              <div className="rounded-lg bg-white/[0.03] p-3">
                <div className="text-[10px] text-slate-500">平均停留</div>
                <div className="mt-1 font-mono text-base font-bold text-tide-300">{fmtDuration(analytics?.avgSessionSec ?? 0)}</div>
              </div>
              <div className="rounded-lg bg-white/[0.03] p-3">
                <div className="text-[10px] text-slate-500">樣本筆數</div>
                <div className="mt-1 font-mono text-base font-bold">{(analytics?.sampleCount ?? 0).toLocaleString()}</div>
              </div>
              <div className="rounded-lg bg-white/[0.03] p-3">
                <div className="text-[10px] text-slate-500">今日 PV</div>
                <div className="mt-1 font-mono text-base font-bold text-tide-300">{analytics?.todayPV ?? 0}</div>
              </div>
              <div className="rounded-lg bg-white/[0.03] p-3">
                <div className="text-[10px] text-slate-500">昨日 PV</div>
                <div className="mt-1 font-mono text-base font-bold">{analytics?.yesterdayPV ?? 0}</div>
              </div>
            </div>
            <div className="mt-3 text-[11px] text-slate-600">平均停留時長 = 每次頁面瀏覽的時間，跨頁導航皆會記錄。最近 3,000 筆為計算基礎。</div>
          </Card>
        </div>
      )}
      {tab === "activity" && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <Stat label="參與會員（有邀請）" value={String((data?.users || []).filter((u) => u.referrals > 0).length)} />
            <Stat label="累計成功邀請" value={String(s?.referralsTotal ?? 0)} tone="up" />
            <Stat label="已發放月數（Plus）" value={String(s?.rewardsTotal ?? 0)} />
          </div>
          <Card className="overflow-x-auto p-0">
            <div className="border-b border-white/5 px-4 py-3 text-sm font-semibold">邀請好友 · 排行榜</div>
            <table className="w-full min-w-[560px] text-left text-xs">
              <thead className="border-b border-white/5 text-slate-500"><tr>
                <th className="px-3 py-2">#</th><th className="px-3 py-2">會員</th><th className="px-3 py-2">UID</th><th className="px-3 py-2">成功邀請</th><th className="px-3 py-2">本輪</th><th className="px-3 py-2">已得月數</th>
              </tr></thead>
              <tbody>
                {(data?.users || []).filter((u) => u.referrals > 0).sort((a, b) => b.referrals - a.referrals).map((u, i) => (
                  <tr key={u.email} className="border-b border-white/5 last:border-0">
                    <td className="px-3 py-2 text-slate-500">{i + 1}</td>
                    <td className="px-3 py-2 text-slate-200">{u.nickname || u.name || "—"}</td>
                    <td className="px-3 py-2 font-mono text-[10px] text-slate-500">{u.uid}</td>
                    <td className="px-3 py-2 font-mono text-tide-200">{u.referrals}</td>
                    <td className="px-3 py-2 text-slate-400">{u.referrals % 5}/5</td>
                    <td className="px-3 py-2 font-mono text-up">{u.referralRewarded ?? 0}</td>
                  </tr>
                ))}
                {(!data?.users || data.users.filter((u) => u.referrals > 0).length === 0) && <tr><td colSpan={6} className="px-3 py-8 text-center text-slate-600">尚無邀請紀錄</td></tr>}
              </tbody>
            </table>
          </Card>
          <Card className="overflow-x-auto p-0">
            <div className="border-b border-white/5 px-4 py-3 text-sm font-semibold">被邀請者 · 來源</div>
            <table className="w-full min-w-[480px] text-left text-xs">
              <thead className="border-b border-white/5 text-slate-500"><tr>
                <th className="px-3 py-2">會員</th><th className="px-3 py-2">UID</th><th className="px-3 py-2">邀請人</th><th className="px-3 py-2">註冊</th>
              </tr></thead>
              <tbody>
                {(data?.users || []).filter((u) => u.invitedBy).map((u) => (
                  <tr key={u.email} className="border-b border-white/5 last:border-0">
                    <td className="px-3 py-2 text-slate-200">{u.nickname || u.name || "—"}</td>
                    <td className="px-3 py-2 font-mono text-[10px] text-slate-500">{u.uid}</td>
                    <td className="px-3 py-2 font-mono text-amber-300">{u.invitedBy}</td>
                    <td className="px-3 py-2 text-slate-500">{fmtTime(u.createdAt)}</td>
                  </tr>
                ))}
                {(!data?.users || data.users.filter((u) => u.invitedBy).length === 0) && <tr><td colSpan={4} className="px-3 py-8 text-center text-slate-600">尚無被邀請紀錄</td></tr>}
              </tbody>
            </table>
          </Card>
        </div>
      )}
      {tab === "users" && (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[680px] text-left text-xs">
            <thead className="border-b border-white/5 text-slate-500"><tr>
              <th className="px-3 py-2">暱稱 / UID</th><th className="px-3 py-2">聯絡</th><th className="px-3 py-2">方案</th><th className="px-3 py-2">到期</th><th className="px-3 py-2">註冊</th><th className="px-3 py-2">設定等級</th>
            </tr></thead>
            <tbody>
              {(data?.users || []).map((u) => (
                <tr key={u.email} className="border-b border-white/5 last:border-0">
                  <td className="px-3 py-2"><div className="flex items-center gap-1 font-medium text-slate-200">{u.nickname || u.name || "—"}{u.emailVerified && <BadgeCheck size={11} className="text-up" />}</div><div className="font-mono text-[10px] text-slate-600">{u.uid} · 邀 {u.referrals ?? 0}</div></td>
                  <td className="px-3 py-2"><div className="text-slate-300">{u.email}</div><div className="text-slate-600">{u.phone || "—"}</div></td>
                  <td className="px-3 py-2"><Badge tone={u.tier === "pro" ? "amber" : u.tier === "air" ? "tide" : "slate"}>{tierUpper(u.tier)}</Badge></td>
                  <td className="px-3 py-2 text-slate-500">{u.planExpiry ? fmtTime(u.planExpiry) : "—"}</td>
                  <td className="px-3 py-2 text-slate-500">{fmtTime(u.createdAt)}</td>
                  <td className="px-3 py-2">
                    <select defaultValue={u.tier + ":" + (u.cycle || "monthly")} onChange={(e) => { const [t, c] = e.target.value.split(":"); setTier(u.email, t, c); }}
                      className="rounded-lg border border-white/10 bg-ink-900 px-2 py-1 text-xs outline-none">
                      <option value="free:monthly">免費</option><option value="air:monthly">Plus · 月</option><option value="air:yearly">Plus · 年</option><option value="pro:monthly">Pro · 月</option><option value="pro:yearly">Pro · 年</option>
                    </select>
                  </td>
                </tr>
              ))}
              {(!data?.users || data.users.length === 0) && <tr><td colSpan={6} className="px-3 py-8 text-center text-slate-600">尚無用戶</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
      {tab === "payments" && (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead className="border-b border-white/5 text-slate-500"><tr>
              <th className="px-3 py-2">時間</th><th className="px-3 py-2">用戶</th><th className="px-3 py-2">方案</th><th className="px-3 py-2">金額</th><th className="px-3 py-2">實付</th><th className="px-3 py-2">狀態</th>
            </tr></thead>
            <tbody>
              {(data?.payments || []).map((p) => (
                <tr key={p.id} className="border-b border-white/5 last:border-0">
                  <td className="px-3 py-2 text-slate-500">{fmtTime(p.createdAt)}</td>
                  <td className="px-3 py-2 text-slate-300">{p.email}</td>
                  <td className="px-3 py-2">{tierUpper(p.tier)} · {p.cycle === "yearly" ? "年" : "月"}</td>
                  <td className="px-3 py-2 font-mono">${p.amount}</td>
                  <td className="px-3 py-2 font-mono text-slate-400">{p.payAmount != null ? p.payAmount + " " + (p.payCurrency || "") : "—"}</td>
                  <td className="px-3 py-2"><Badge tone={payTone(p.status)}>{p.status}</Badge></td>
                </tr>
              ))}
              {(!data?.payments || data.payments.length === 0) && <tr><td colSpan={6} className="px-3 py-8 text-center text-slate-600">尚無付款紀錄</td></tr>}
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
                <Badge tone={f.tier === "pro" ? "amber" : f.tier === "air" ? "tide" : "slate"}>{tierUpper(f.tier)}</Badge>
                <span className="text-slate-500">{f.email}</span><span className="text-slate-600">{f.phone}</span>
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
