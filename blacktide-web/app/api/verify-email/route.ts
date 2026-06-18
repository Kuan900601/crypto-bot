export const dynamic = "force-dynamic";
import { redisGet, redisCmd } from "@/lib/redis";
import { getUser, saveUser } from "@/lib/auth";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const token = searchParams.get("token") || "";
  const base = process.env.NEXTAUTH_URL || "";
  if (!token) return Response.redirect(base + "/login?verifyError=1");
  try {
    const email = await redisGet("email:verify:" + token);
    if (!email) return Response.redirect(base + "/login?verifyError=1");
    const u = await getUser(email);
    if (u) {
      u.emailVerified = true;
      u.requiresEmailVerification = false;
      await saveUser(u);
    }
    try { await redisCmd(["DEL", "email:verify:" + token]); } catch {}
    return Response.redirect(base + "/login?verified=1");
  } catch {
    return Response.redirect(base + "/login?verifyError=1");
  }
}
