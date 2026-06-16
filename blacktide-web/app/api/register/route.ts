import bcrypt from "bcryptjs";
import { getUser, getEmailByUid, newUser, saveUser, grantAirMonths } from "@/lib/auth";
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
    return Response.json({ ok: true, uid: u.uid });
  } catch {
    return Response.json({ error: "註冊失敗，請稍後再試" }, { status: 500 });
  }
}
