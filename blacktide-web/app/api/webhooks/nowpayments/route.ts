import crypto from "crypto";
import { getUser, saveUser } from "@/lib/auth";
import { redisGet, redisSet, redisLPush } from "@/lib/redis";
import { priceOf } from "@/lib/access";
export const dynamic = "force-dynamic";
function sortedStringify(obj: Record<string, unknown>): string {
  return JSON.stringify(obj, Object.keys(obj).sort());
}
export async function POST(req: Request) {
  const secret = process.env.NOWPAYMENTS_IPN_SECRET;
  const raw = await req.text();
  let body: Record<string, unknown>;
  try { body = JSON.parse(raw); } catch { return new Response("bad json", { status: 400 }); }
  if (secret) {
    const sig = req.headers.get("x-nowpayments-sig") || "";
    const expected = crypto.createHmac("sha512", secret).update(sortedStringify(body)).digest("hex");
    if (sig !== expected) return new Response("invalid signature", { status: 401 });
  }
  const status = String(body.payment_status || "");
  const orderId = String(body.order_id || "");
  if (!orderId) return new Response("ok", { status: 200 });
  const orderRaw = await redisGet("web:order:" + orderId);
  if (!orderRaw) return new Response("ok", { status: 200 });
  const order = JSON.parse(orderRaw) as { email: string; tier: "air" | "pro"; cycle: "monthly" | "yearly"; amount: number; status: string };
  await redisLPush("web:payments", JSON.stringify({
    id: "pay_" + Date.now() + "_" + Math.floor(Math.random() * 1000),
    orderId, email: order.email, tier: order.tier, cycle: order.cycle, amount: order.amount,
    payAmount: body.actually_paid ?? body.pay_amount ?? null, payCurrency: body.pay_currency ?? null,
    status, paymentId: body.payment_id ?? null, createdAt: new Date().toISOString(),
  }));
  if (status === "finished" && order.status !== "paid") {
    const u = await getUser(order.email);
    if (u) {
      u.tier = order.tier; u.plan = "premium"; u.cycle = order.cycle;
      u.subAmount = priceOf(order.tier, order.cycle); u.subStartedAt = new Date().toISOString();
      const days = order.cycle === "yearly" ? 365 : 30;
      u.planExpiry = new Date(Date.now() + days * 86400000).toISOString();
      await saveUser(u);
    }
    order.status = "paid";
    await redisSet("web:order:" + orderId, JSON.stringify(order));
  }
  return new Response("ok", { status: 200 });
}
