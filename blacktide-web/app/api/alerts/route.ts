import { NextResponse } from "next/server";
import { ALERTS } from "@/lib/mock";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({ alerts: ALERTS });
}
