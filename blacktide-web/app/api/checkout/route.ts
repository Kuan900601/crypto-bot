import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { priceOf } from "@/lib/access";
export async function POST(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) return Response.json({ error: "請先登入" }, { status: 401 });
  const { tier, cycle } = await req.json().catch(() => ({ tier: "air", cycle: "monthly" }));
  const t: "air" | "pro" = tier === "pro" ? "pro" : "air";
  const c: "monthly" | "yearly" = cycle === "yearly" ? "yearly" : "monthly";
  const amount = priceOf(t, c);
  return Response.json({
    todo: true, tier: t, cycle: c, amount,
    message: `已選擇 ${t === "pro" ? "Pro" : "Air"} · ${c === "yearly" ? "年繳" : "月繳"} ${amount} USD。線上加密金流（NOWPayments）即將開放；目前可由管理員手動開通，或透過會員中心反饋聯繫。`,
  });
}
