import { getServerSession } from "next-auth";
import { authOptions, getUser, saveUser } from "@/lib/auth";
import { redisGet, redisSet } from "@/lib/redis";
export const dynamic = "force-dynamic";
const CODEKEY = (e: string) => "web:vcode:email:" + e.trim().toLowerCase();
async function sendEmail(to: string, code: string): Promise<{ ok: boolean; info: string }> {
  const key = process.env.RESEND_API_KEY;
  if (!key) return { ok: false, info: "no_key" };
  const from = process.env.RESEND_FROM || "黑潮 BLACKTIDE <onboarding@resend.dev>";
  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST", headers: { Authorization: "Bearer " + key, "Content-Type": "application/json" },
      body: JSON.stringify({ from, to, subject: "黑潮 BLACKTIDE 信箱驗證碼",
        html: "<div style='font-family:sans-serif'><p>您好，您的信箱驗證碼為：</p><p style='font-size:24px;font-weight:bold;letter-spacing:4px'>" + code + "</p><p>10 分鐘內有效。</p></div>" }),
    });
    if (r.ok) return { ok: true, info: "" };
    let msg = "HTTP " + r.status;
    try { const e = await r.json(); if (e?.message) msg = String(e.message); } catch {}
    return { ok: false, info: msg };
  } catch { return { ok: false, info: "network_error" }; }
}
export async function POST(req: Request) {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) return Response.json({ error: "未登入" }, { status: 401 });
  const { action, code } = await req.json().catch(() => ({}));
  const u = await getUser(email);
  if (!u) return Response.json({ error: "查無帳號" }, { status: 404 });
  if (action === "send") {
    const c = Math.floor(100000 + Math.random() * 900000).toString();
    await redisSet(CODEKEY(email), JSON.stringify({ code: c, exp: Date.now() + 600000 }));
    const res = await sendEmail(email, c);
    return Response.json({ ok: true, configured: !!process.env.RESEND_API_KEY, sent: res.ok, info: res.info });
  }
  if (action === "check") {
    const saved = await redisGet(CODEKEY(email));
    if (!saved) return Response.json({ error: "驗證碼已過期，請重新發送" }, { status: 400 });
    let o: { code: string; exp: number };
    try { o = JSON.parse(saved); } catch { return Response.json({ error: "驗證碼無效" }, { status: 400 }); }
    if (Date.now() > o.exp) return Response.json({ error: "驗證碼已過期，請重新發送" }, { status: 400 });
    if (String(code || "").trim() !== o.code) return Response.json({ error: "驗證碼錯誤" }, { status: 400 });
    u.emailVerified = true; await saveUser(u);
    return Response.json({ ok: true });
  }
  return Response.json({ error: "未知操作" }, { status: 400 });
}
