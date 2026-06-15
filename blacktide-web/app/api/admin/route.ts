import { getServerSession } from "next-auth";
import { authOptions, getUser, saveUser, tierOf, USERS_SET } from "@/lib/auth";
import { redisSMembers, redisLRange } from "@/lib/redis";
import { priceOf, monthlyEquivalent } from "@/lib/access";
export const dynamic = "force-dynamic";
async function requireAdmin() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email || !session.user.isAdmin) return null;
  return session.user.email;
}
export async function GET() {
  if (!(await requireAdmin())) return Response.json({ error: "無權限" }, { status: 403 });
  const emails = await redisSMembers(USERS_SET);
  const users: { email: string; name: string; phone: string; uid: string; tier: string; cycle?: string; subAmount?: number; createdAt: string }[] = [];
  for (const e of emails) {
    const u = await getUser(e);
    if (!u) continue;
    users.push({ email: u.email, name: u.name, phone: u.phone || "", uid: u.uid, tier: tierOf(u), cycle: u.cycle, subAmount: u.subAmount, createdAt: u.createdAt });
  }
  users.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  const air = users.filter((u) => u.tier === "air");
  const pro = users.filter((u) => u.tier === "pro");
  const subs = [...air, ...pro];
  const mrr = subs.reduce((s, u) => s + monthlyEquivalent(u.tier as "air" | "pro", (u.cycle as "monthly" | "yearly") || "monthly"), 0);
  const recorded = subs.reduce((s, u) => s + (u.subAmount || 0), 0);
  const fbRaw = await redisLRange("web:feedback", 0, 499);
  const feedback = fbRaw.map((s) => { try { return JSON.parse(s); } catch { return null; } }).filter(Boolean);
  return Response.json({
    stats: { totalUsers: users.length, free: users.length - subs.length, air: air.length, pro: pro.length, mrr, recorded },
    users, feedback,
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
  if (t === "free") { u.cycle = undefined; u.subAmount = 0; u.subStartedAt = undefined; }
  else { const c: "monthly" | "yearly" = cycle === "yearly" ? "yearly" : "monthly"; u.cycle = c; u.subAmount = priceOf(t, c); u.subStartedAt = new Date().toISOString(); }
  await saveUser(u);
  return Response.json({ ok: true, tier: t });
}
