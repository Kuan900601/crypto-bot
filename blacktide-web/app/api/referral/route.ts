import { getServerSession } from "next-auth";
import { authOptions, getUser } from "@/lib/auth";
export const dynamic = "force-dynamic";
export async function GET() {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) return Response.json({ error: "未登入" }, { status: 401 });
  const u = await getUser(email);
  if (!u) return Response.json({ error: "查無帳號" }, { status: 404 });
  const referrals = u.referrals || 0;
  const rewarded = u.referralRewarded || 0;
  const rem = referrals % 5;
  return Response.json({ uid: u.uid, referrals, rewarded, monthsEarned: rewarded, inThisCycle: rem, toNext: 5 - rem });
}
