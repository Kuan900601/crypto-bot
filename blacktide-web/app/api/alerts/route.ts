import { ALERTS } from "@/lib/mock";
export const dynamic = "force-dynamic";
export async function GET() {
  return Response.json({ alerts: ALERTS, source: "mock" });
}
