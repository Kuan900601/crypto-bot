import { NextResponse } from "next/server";
import { NEWS } from "@/lib/mock";

export const dynamic = "force-dynamic";

// Mock 新聞。bot 的新聞模組（ANTHROPIC_API_KEY + CRYPTOPANIC_TOKEN）目前擱置，故先用模擬資料。
export async function GET() {
  return NextResponse.json({ news: NEWS });
}
