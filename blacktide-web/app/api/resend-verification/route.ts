import { getServerSession } from "next-auth";
import { authOptions, getUser } from "@/lib/auth";
import { redisCmd } from "@/lib/redis";
import { sendVerificationEmail } from "@/lib/email";

export async function POST() {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) return Response.json({ error: "請先登入" }, { status: 401 });
  const u = await getUser(email);
  if (!u) return Response.json({ error: "找不到帳號" }, { status: 404 });
  if (u.emailVerified) return Response.json({ ok: true, alreadyVerified: true });
  const token = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2) + Date.now().toString(36);
  try { await redisCmd(["SETEX", "email:verify:" + token, "86400", email.trim().toLowerCase()]); } catch {}
  await sendVerificationEmail(email, token);
  return Response.json({ ok: true });
}
