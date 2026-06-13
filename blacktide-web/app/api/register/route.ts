import { NextRequest, NextResponse } from "next/server";
import { createUser } from "@/lib/users";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  try {
    const { email, password, name } = (await req.json()) as {
      email?: string; password?: string; name?: string;
    };
    if (!email || !/.+@.+\..+/.test(email)) {
      return NextResponse.json({ error: "BAD_EMAIL" }, { status: 400 });
    }
    if (!password || password.length < 6) {
      return NextResponse.json({ error: "WEAK_PASSWORD" }, { status: 400 });
    }
    await createUser(email, name || "", password);
    return NextResponse.json({ ok: true });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: msg }, { status: msg === "EMAIL_TAKEN" ? 409 : 500 });
  }
}
