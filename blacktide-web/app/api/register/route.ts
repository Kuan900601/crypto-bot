import bcrypt from "bcryptjs";
import { getUser, getEmailByUid, newUser, saveUser, grantAirMonths } from "@/lib/auth";
import { redisCmd } from "@/lib/redis";

async function sendVerificationEmail(email: string, token: string) {
  const key = process.env.RESEND_API_KEY;
  const base = process.env.NEXTAUTH_URL || "https://app.blacktide.cc";
  if (!key) return;
  const link = `${base}/api/verify-email?token=${token}`;
  await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: "Bearer " + key, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: "noreply@mail.blacktide.cc",
      to: email,
      subject: "【黑潮 BLACKTIDE】驗證您的帳號 Email",
      html: `<div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;background:#0a0c12;color:#e2e8f0;border-radius:16px">
        <h2 style="color:#e0bf5e;margin-bottom:8px">黑潮 BLACKTIDE</h2>
        <p style="color:#94a3b8;font-size:13px">感謝您註冊！請點擊下方按鈕驗證您的 Email，連結 24 小時內有效。</p>
        <a href="${link}" style="display:inline-block;margin-top:20px;padding:12px 28px;background:#d4af37;color:#0a0c12;border-radius:8px;font-weight:700;text-decoration:none;font-size:14px">驗證 Email</a>
        <p style="margin-top:20px;color:#475569;font-size:11px">若您沒有在黑潮平台註冊，請忽略此信。</p>
      </div>`,
    }),
  }).catch(() => {});
}

export async function POST(req: Request) {
  try {
    const { email, password, nickname, phone, avatar, inviterUid } = await req.json();
    if (!nickname || !String(nickname).trim()) return Response.json({ error: "請填寫暱稱" }, { status: 400 });
    if (!email || !/.+@.+\..+/.test(email)) return Response.json({ error: "Email 格式不正確" }, { status: 400 });
    if (!phone || String(phone).replace(/\D/g, "").length < 6) return Response.json({ error: "請填寫有效手機號碼" }, { status: 400 });
    if (!password || String(password).length < 8) return Response.json({ error: "密碼至少 8 碼" }, { status: 400 });
    if (await getUser(email)) return Response.json({ error: "此 Email 已註冊" }, { status: 409 });
    const av = typeof avatar === "string" && avatar.length < 200000 ? avatar : "";
    const inv = typeof inviterUid === "string" ? inviterUid.trim().toUpperCase() : "";
    const u = newUser(email, String(nickname), await bcrypt.hash(String(password), 10), String(phone), av, inv);
    // Mark new users as requiring email verification
    if (!u.isAdmin) {
      u.requiresEmailVerification = true;
      u.emailVerified = false;
    }
    await saveUser(u);
    if (inv && inv !== u.uid) {
      const invEmail = await getEmailByUid(inv);
      if (invEmail) {
        const inviter = await getUser(invEmail);
        if (inviter) {
          inviter.referrals = (inviter.referrals || 0) + 1;
          const due = Math.floor(inviter.referrals / 5);
          const got = inviter.referralRewarded || 0;
          if (due > got) { grantAirMonths(inviter, due - got); inviter.referralRewarded = due; }
          await saveUser(inviter);
        }
      }
    }
    // Generate and store verification token (24h TTL)
    const token = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2) + Date.now().toString(36);
    try {
      await redisCmd(["SETEX", "email:verify:" + token, "86400", email.trim().toLowerCase()]);
    } catch {}
    await sendVerificationEmail(email, token);
    return Response.json({ ok: true, uid: u.uid, emailPending: !u.isAdmin });
  } catch {
    return Response.json({ error: "註冊失敗，請稍後再試" }, { status: 500 });
  }
}
