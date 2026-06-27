import { getServerSession } from "next-auth";
import { authOptions, getUser, getUserWithSource, saveUser, tierOf } from "@/lib/auth";
import { redisGet, redisSet } from "@/lib/redis";
export const dynamic = "force-dynamic";
const NOTIFYKEY = (e: string) => "web:notify:" + e.trim().toLowerCase();
async function current() {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) return null;
  return getUser(email);
}
export async function GET() {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) return Response.json({ error: "未登入", source: "none" }, { status: 401 });
  const { user: u, source } = await getUserWithSource(email);
  if (!u) return Response.json({ error: "未登入", source }, { status: 401 });
  let notify = { enabled: true, quietStart: "", quietEnd: "" };
  try { const raw = await redisGet(NOTIFYKEY(u.email)); if (raw) notify = { ...notify, ...JSON.parse(raw) }; } catch {}
  return Response.json({
    uid: u.uid, email: u.email, nickname: u.nickname || u.name, phone: u.phone || "", avatar: u.avatar || "",
    tier: tierOf(u), cycle: u.cycle || null, subAmount: u.subAmount || 0, planExpiry: u.planExpiry || null,
    emailVerified: !!u.emailVerified, phoneVerified: !!u.phoneVerified,
    invitedBy: u.invitedBy || "", referrals: u.referrals || 0, referralRewarded: u.referralRewarded || 0,
    notifyEnabled: notify.enabled, quietStart: notify.quietStart, quietEnd: notify.quietEnd,
    isAdmin: !!u.isAdmin, isFounder: !!u.isFounder, createdAt: u.createdAt,
    source, // 診斷用："redis"=真資料／"memory"=Redis讀不到、退回暫存（重啟即消失）／"none"=查無紀錄
  });
}
export async function POST(req: Request) {
  const u = await current();
  if (!u) return Response.json({ error: "未登入" }, { status: 401 });
  const body = await req.json().catch(() => ({}));
  if (typeof body.nickname === "string" && body.nickname.trim()) { u.nickname = body.nickname.trim().slice(0, 40); u.name = u.nickname; }
  if (typeof body.phone === "string") u.phone = body.phone.trim().slice(0, 30);
  if (typeof body.avatar === "string" && body.avatar.length < 200000) u.avatar = body.avatar;
  if (body.notify && typeof body.notify === "object") {
    const n = body.notify;
    const notify = {
      enabled: !!n.enabled,
      quietStart: typeof n.quietStart === "string" ? n.quietStart.slice(0, 5) : "",
      quietEnd: typeof n.quietEnd === "string" ? n.quietEnd.slice(0, 5) : "",
    };
    await redisSet(NOTIFYKEY(u.email), JSON.stringify(notify));
  }
  await saveUser(u);
  return Response.json({ ok: true });
}
