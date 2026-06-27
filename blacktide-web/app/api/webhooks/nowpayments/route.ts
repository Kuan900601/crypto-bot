import crypto from "crypto";
import { getUser, saveUser } from "@/lib/auth";
import { redisGet, redisSet, redisLPush, redisCmd } from "@/lib/redis";
import { priceOf, FOUNDER } from "@/lib/access";
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
  const order = JSON.parse(orderRaw) as { email: string; tier: "air" | "pro" | "founder"; cycle: "monthly" | "yearly"; amount: number; status: string };
  await redisLPush("web:payments", JSON.stringify({
    id: "pay_" + Date.now() + "_" + Math.floor(Math.random() * 1000),
    orderId, email: order.email, tier: order.tier, cycle: order.cycle, amount: order.amount,
    payAmount: body.actually_paid ?? body.pay_amount ?? null, payCurrency: body.pay_currency ?? null,
    status, paymentId: body.payment_id ?? null, createdAt: new Date().toISOString(),
  }));
  if (status === "finished" && order.status !== "paid") {
    const u = await getUser(order.email);
    if (u) {
      if (order.tier === "founder") {
        // 用 Redis INCR 做原子計數，避免「checkout 時還沒滿、幾乎同時付款完成」的競態超賣
        // （checkout 端的名額檢查是建立訂單時的第一層擋，這裡才是真正核發福利前的最終守門）。
        let oversold = false;
        try {
          const newCount = await redisCmd(["INCR", "founder:slots:sold"]);
          if (typeof newCount === "number" && newCount > FOUNDER.slots) {
            oversold = true;
            await redisCmd(["DECR", "founder:slots:sold"]); // 退回計數，不佔用名額（名額代表「已核發」，不是「已嘗試」）
          }
        } catch {}
        if (oversold) {
          // 已收到款項但名額已滿：不核發創始福利，留證據給作者人工處理（退款或加開名額）
          await redisLPush("web:founder:oversold", JSON.stringify({
            orderId, email: order.email, amount: order.amount, at: new Date().toISOString(),
          }));
        } else {
          u.isFounder = true;
          u.tier = "pro"; u.plan = "premium"; u.cycle = "yearly";
          u.subAmount = order.amount; u.subStartedAt = new Date().toISOString();
          u.isTrial = false;
          u.planExpiry = new Date(Date.now() + 365 * 86400000).toISOString();
        }
      } else {
        u.tier = order.tier; u.plan = "premium"; u.cycle = order.cycle;
        u.subAmount = priceOf(order.tier, order.cycle); u.subStartedAt = new Date().toISOString();
        u.isTrial = false;
        const days = order.cycle === "yearly" ? 365 : 30;
        u.planExpiry = new Date(Date.now() + days * 86400000).toISOString();
      }
      await saveUser(u);
    }
    order.status = "paid";
    await redisSet("web:order:" + orderId, JSON.stringify(order));
  }
  return new Response("ok", { status: 200 });
}
