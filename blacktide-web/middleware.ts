import { NextRequest, NextResponse } from "next/server";

// 儀表板存取閘門（HTTP Basic Auth）。
// 沿用 bot 慣例：DASH_PASSWORD 未設 → 放行（公開，等同 demo）；設了 → 要密碼才看得到。
// 帳號可隨意輸入，只驗密碼。Vercel 走 HTTPS，憑證不會明文外洩。
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
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
