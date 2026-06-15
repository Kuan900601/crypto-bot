import { getServerSession } from "next-auth";
import { authOptions, getUser, tierOf } from "@/lib/auth";
import { redisLPush } from "@/lib/redis";
export async function POST(req: Request) {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) return Response.json({ error: "未登入" }, { status: 401 });
  const { content } = await req.json().catch(() => ({}));
  if (!content || !String(content).trim()) return Response.json({ error: "請填寫反饋內容" }, { status: 400 });
  const u = await getUser(email);
  const rec = {
    id: "fb_" + Date.now() + "_" + Math.floor(Math.random() * 1000),
    email, name: u?.name || "", phone: u?.phone || "", uid: u?.uid || "",
    tier: tierOf(u), content: String(content).slice(0, 4000), createdAt: new Date().toISOString(),
  };
  await redisLPush("web:feedback", JSON.stringify(rec));
  return Response.json({ ok: true });
}
