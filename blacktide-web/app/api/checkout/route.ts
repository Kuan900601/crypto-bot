import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

export const runtime = "nodejs";

// 建立 NOWPayments 託管發票（hosted invoice），回傳 invoice_url 讓前端導轉。
// 付款結果由 /api/nowpayments/ipn 的 webhook 確認後才升級會員（不靠 success_url 判定）。
export async function POST() {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) return NextResponse.json({ error: "UNAUTH" }, { status: 401 });

  const apiKey = process.env.NOWPAYMENTS_API_KEY;
  if (!apiKey) return NextResponse.json({ error: "NO_GATEWAY" }, { status: 503 });

  const price = Number(process.env.PREMIUM_PRICE_USD || "29");
  const base = (process.env.NEXTAUTH_URL || "").replace(/\/$/, "");

  try {
    const r = await fetch("https://api.nowpayments.io/v1/invoice", {
      method: "POST",
      headers: { "x-api-key": apiKey, "Content-Type": "application/json" },
      body: JSON.stringify({
        price_amount: price,
        price_currency: "usd",
        // order_id 夾帶 email，IPN 回來才知道幫誰升級
        order_id: `premium:${email}:${Date.now()}`,
        order_description: "BlackTide Premium 30 天",
        ipn_callback_url: base ? `${base}/api/nowpayments/ipn` : undefined,
        success_url: base ? `${base}/account?paid=1` : undefined,
        cancel_url: base ? `${base}/pricing?canceled=1` : undefined,
      }),
    });
    const j = await r.json();
    if (!r.ok || !j?.invoice_url) {
      return NextResponse.json({ error: j?.message || "INVOICE_FAIL" }, { status: 502 });
    }
    return NextResponse.json({ url: j.invoice_url });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
