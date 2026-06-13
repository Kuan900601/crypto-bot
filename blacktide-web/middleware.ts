import { NextRequest, NextResponse } from "next/server";

// 儀表板「私人模式」閘門（HTTP Basic Auth）。
// 沿用 bot 慣例：DASH_PASSWORD 未設 → 放行（公開）；設了 → 整站要密碼。
// ⚠️ 會員收費模式（NextAuth）應讓站台公開，故請「不要」設 DASH_PASSWORD；
//    兩者是互斥的存取模式。為保險，登入/驗證/金流 webhook 路徑一律排除在 Basic Auth 外。
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|login|api/auth|api/nowpayments).*)"],
};

export function middleware(req: NextRequest) {
  const pw = process.env.DASH_PASSWORD;
  if (!pw) return NextResponse.next(); // 未設 = 不設防

  const auth = req.headers.get("authorization");
  if (auth) {
    const [scheme, encoded] = auth.split(" ");
    if (scheme === "Basic" && encoded) {
      try {
        const decoded = atob(encoded);
        const pass = decoded.slice(decoded.indexOf(":") + 1);
        if (pass === pw) return NextResponse.next();
      } catch {
        // 解碼失敗 → 視為未授權，往下走
      }
    }
  }

  return new NextResponse("需要密碼才能存取黑潮儀表板", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="BlackTide Dashboard", charset="UTF-8"' },
  });
}
