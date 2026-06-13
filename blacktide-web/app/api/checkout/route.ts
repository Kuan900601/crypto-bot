import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
export async function POST(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) return Response.json({ error: "請先登入" }, { status: 401 });
  const { plan } = await req.json().catch(() => ({ plan: "monthly" }));
  // 金流接縫（拿到 NOWPayments 金鑰後在此實作 invoice 建單；webhook 放 /api/webhooks/nowpayments）
  // 並在 signals 等付費 API 加 getServerSession + isPremium 伺服器端檢查。
  return Response.json({
    todo: true, plan,
    message: "金流尚未接通：需先申請 NOWPayments 商家帳號與金鑰（接縫已預留在此路由註解）。會員系統其餘功能可正常使用。",
  }, { status: 501 });
}
