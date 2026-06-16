import { getServerSession } from "next-auth";
import { authOptions, getUser, saveUser, tierOf } from "@/lib/auth";
export const dynamic = "force-dynamic";
async function current() {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) return null;
  return getUser(email);
}
export async function GET() {
  const u = await current();
  if (!u) return Response.json({ error: "未登入" }, { status: 401 });
  return Response.json({
    uid: u.uid, email: u.email, nickname: u.nickname || u.name, phone: u.phone || "", avatar: u.avatar || "",
    tier: tierOf(u), cycle: u.cycle || null, subAmount: u.subAmount || 0, planExpiry: u.planExpiry || null,
    emailVerified: !!u.emailVerified, phoneVerified: !!u.phoneVerified,
    invitedBy: u.invitedBy || "", referrals: u.referrals || 0, referralRewarded: u.referralRewarded || 0,
    isAdmin: !!u.isAdmin, createdAt: u.createdAt,
  });
}
export async function POST(req: Request) {
  const u = await current();
  if (!u) return Response.json({ error: "未登入" }, { status: 401 });
  const body = await req.json().catch(() => ({}));
  if (typeof body.nickname === "string" && body.nickname.trim()) { u.nickname = body.nickname.trim().slice(0, 40); u.name = u.nickname; }
  if (typeof body.phone === "string") u.phone = body.phone.trim().slice(0, 30);
  if (typeof body.avatar === "string" && body.avatar.length < 200000) u.avatar = body.avatar;
  await saveUser(u);
  return Response.json({ ok: true });
}
