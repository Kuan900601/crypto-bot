import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { upgradeUser } from "@/lib/users";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// NOWPayments IPN webhook。驗證 HMAC-SHA512 簽章（key 依字母排序後 stringify），
// 只有付款狀態為 finished/confirmed 才升級會員。設了 NOWPAYMENTS_IPN_SECRET 才驗簽（強烈建議設）。

// 遞迴依 key 排序，與 NOWPayments 簽章規則一致
function sortDeep(o: unknown): unknown {
  if (Array.isArray(o)) return o.map(sortDeep);
  if (o && typeof o === "object") {
    return Object.keys(o as Record<string, unknown>)
      .sort()
      .reduce((acc, k) => {
        acc[k] = sortDeep((o as Record<string, unknown>)[k]);
        return acc;
      }, {} as Record<string, unknown>);
  }
  return o;
}

export async function POST(req: NextRequest) {
  const raw = await req.text();
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "BAD_JSON" }, { status: 400 });
  }

  const secret = process.env.NOWPAYMENTS_IPN_SECRET;
  if (secret) {
    const sig = req.headers.get("x-nowpayments-sig") || "";
    const expected = crypto
      .createHmac("sha512", secret)
      .update(JSON.stringify(sortDeep(payload)))
      .digest("hex");
    const a = Buffer.from(sig);
    const b = Buffer.from(expected);
    if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
      return NextResponse.json({ error: "BAD_SIGNATURE" }, { status: 401 });
    }
  }

  const status = String(payload.payment_status || "");
  const orderId = String(payload.order_id || "");
  // order_id 格式：premium:<email>:<ts>
  if ((status === "finished" || status === "confirmed") && orderId.startsWith("premium:")) {
    const email = orderId.split(":")[1];
    if (email) {
      const days = Number(process.env.PREMIUM_DAYS || "30");
      await upgradeUser(email, days);
    }
  }

  // 一律回 200，避免 NOWPayments 重送（驗簽失敗已在上面擋掉）
  return NextResponse.json({ ok: true });
}
