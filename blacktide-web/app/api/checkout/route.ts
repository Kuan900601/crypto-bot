import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { priceOf } from "@/lib/access";
import { redisSet } from "@/lib/redis";
const NP = "https://api.nowpayments.io/v1";
function baseUrl() { return process.env.NEXTAUTH_URL || process.env.NEXT_PUBLIC_SITE_URL || ""; }
export async function POST(req: Request) {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) return Response.json({ error: "請先登入" }, { status: 401 });
  const { tier, cycle } = await req.json().catch(() => ({ tier: "air", cycle: "monthly" }));
  const t: "air" | "pro" = tier === "pro" ? "pro" : "air";
  const c: "monthly" | "yearly" = cycle === "yearly" ? "yearly" : "monthly";
  const amount = priceOf(t, c);
  const key = process.env.NOWPAYMENTS_API_KEY;
  if (!key) {
    return Response.json({ todo: true, manual: true, tier: t, cycle: c, amount,
      message: "已選擇 " + (t === "pro" ? "Pro" : "Air") + " · " + (c === "yearly" ? "年繳" : "月繳") + " " + amount + " USD。線上金流尚未設定（NOWPAYMENTS_API_KEY），目前可由管理員手動開通。" });
  }
  const orderId = "bt_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 8);
  await redisSet("web:order:" + orderId, JSON.stringify({ orderId, email, tier: t, cycle: c, amount, status: "pending", createdAt: new Date().toISOString() }));
  const base = baseUrl();
  try {
    const r = await fetch(NP + "/invoice", {
      method: "POST",
      headers: { "x-api-key": key, "Content-Type": "application/json" },
      body: JSON.stringify({
        price_amount: amount, price_currency: "usd",
        order_id: orderId,
        order_description: "黑潮 BLACKTIDE " + t.toUpperCase() + " " + (c === "yearly" ? "年繳" : "月繳"),
        ipn_callback_url: base ? base + "/api/webhooks/nowpayments" : undefined,
        success_url: base ? base + "/member?paid=1" : undefined,
        cancel_url: base ? base + "/member" : undefined,
      }),
    });
    const d = await r.json();
    if (d && d.invoice_url) return Response.json({ ok: true, url: d.invoice_url, amount, tier: t, cycle: c });
    return Response.json({ error: "建立付款失敗：" + (d?.message || "請確認 NOWPayments 設定") }, { status: 502 });
  } catch {
    return Response.json({ error: "無法連線金流服務，請稍後再試" }, { status: 502 });
  }
}
