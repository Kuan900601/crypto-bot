import { getServerSession } from "next-auth";
import { authOptions, getUser, saveUser, tierOf, USERS_SET } from "@/lib/auth";
import { redisSMembers, redisLRange } from "@/lib/redis";
import { priceOf, monthlyEquivalent } from "@/lib/access";
export const dynamic = "force-dynamic";
/* eslint-disable @typescript-eslint/no-explicit-any */
async function requireAdmin() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email || !session.user.isAdmin) return null;
  return session.user.email;
}
export async function GET() {
  if (!(await requireAdmin())) return Response.json({ error: "無權限" }, { status: 403 });
  const emails = await redisSMembers(USERS_SET);
  const users: { email: string; name: string; phone: string; uid: string; tier: string; cycle?: string; subAmount?: number; planExpiry?: string; createdAt: string }[] = [];
  for (const e of emails) {
    const u = await getUser(e);
    if (!u) continue;
    users.push({ email: u.email, name: u.name, phone: u.phone || "", uid: u.uid, tier: tierOf(u), cycle: u.cycle, subAmount: u.subAmount, planExpiry: u.planExpiry, createdAt: u.createdAt });
  }
  users.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  const air = users.filter((u) => u.tier === "air");
  const pro = users.filter((u) => u.tier === "pro");
  const subs = [...air, ...pro];
  const mrr = subs.reduce((s, u) => s + monthlyEquivalent(u.tier as "air" | "pro", (u.cycle as "monthly" | "yearly") || "monthly"), 0);
  const recorded = subs.reduce((s, u) => s + (u.subAmount || 0), 0);
  const now = new Date();
  const byDay: { date: string; count: number }[] = [];
  for (let i = 13; i >= 0; i--) {
    const d = new Date(now); d.setDate(d.getDate() - i);
    const k = d.toISOString().slice(0, 10);
    byDay.push({ date: k.slice(5), count: users.filter((u) => (u.createdAt || "").slice(0, 10) === k).length });
  }
  const weekAgo = Date.now() - 7 * 86400000;
  const signups7d = users.filter((u) => new Date(u.createdAt || 0).getTime() >= weekAgo).length;
  const payRaw = await redisLRange("web:payments", 0, 499);
  const payments = payRaw.map((s) => { try { return JSON.parse(s); } catch { return null; } }).filter(Boolean) as any[];
  const revenuePaid = payments.filter((p) => p.status === "finished").reduce((s, p) => s + (p.amount || 0), 0);
  const conversion = users.length ? Math.round((subs.length / users.length) * 1000) / 10 : 0;
  const arpu = subs.length ? Math.round(recorded / subs.length) : 0;
  const fbRaw = await redisLRange("web:feedback", 0, 499);
  const feedback = fbRaw.map((s) => { try { return JSON.parse(s); } catch { return null; } }).filter(Boolean);
  return Response.json({
    stats: { totalUsers: users.length, free: users.length - subs.length, air: air.length, pro: pro.length, mrr, recorded, signups7d, byDay, revenuePaid, conversion, arpu },
    users, feedback, payments,
  });
}
export async function POST(req: Request) {
  if (!(await requireAdmin())) return Response.json({ error: "無權限" }, { status: 403 });
  const { email, tier, cycle } = await req.json().catch(() => ({}));
  if (!email) return Response.json({ error: "缺少 email" }, { status: 400 });
  const u = await getUser(email);
  if (!u) return Response.json({ error: "查無此用戶" }, { status: 404 });
  const t: "free" | "air" | "pro" = tier === "pro" ? "pro" : tier === "air" ? "air" : "free";
  u.tier = t;
  u.plan = t === "free" ? "free" : "premium";
  if (t === "free") { u.cycle = undefined; u.subAmount = 0; u.subStartedAt = undefined; u.planExpiry = undefined; }
  else {
    const c: "monthly" | "yearly" = cycle === "yearly" ? "yearly" : "monthly";
    u.cycle = c; u.subAmount = priceOf(t, c); u.subStartedAt = new Date().toISOString();
    u.planExpiry = new Date(Date.now() + (c === "yearly" ? 365 : 30) * 86400000).toISOString();
  }
  await saveUser(u);
  return Response.json({ ok: true, tier: t });
}
