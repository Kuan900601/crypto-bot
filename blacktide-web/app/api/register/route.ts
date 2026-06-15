import bcrypt from "bcryptjs";
import { getUser, newUser, saveUser } from "@/lib/auth";
export async function POST(req: Request) {
  try {
    const { email, password, name, phone, avatar } = await req.json();
    if (!email || !/.+@.+\..+/.test(email)) return Response.json({ error: "Email 格式不正確" }, { status: 400 });
    if (!password || String(password).length < 8) return Response.json({ error: "密碼至少 8 碼" }, { status: 400 });
    if (await getUser(email)) return Response.json({ error: "此 Email 已註冊" }, { status: 409 });
    const av = typeof avatar === "string" && avatar.length < 200000 ? avatar : "";
    const u = newUser(email, name || "", await bcrypt.hash(String(password), 10), typeof phone === "string" ? phone : "", av);
    await saveUser(u);
    return Response.json({ ok: true });
  } catch {
    return Response.json({ error: "註冊失敗，請稍後再試" }, { status: 500 });
  }
}
