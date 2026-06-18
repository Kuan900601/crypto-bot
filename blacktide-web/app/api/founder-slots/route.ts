import { redisGet } from "@/lib/redis";
import { FOUNDER } from "@/lib/access";
export const dynamic = "force-dynamic";
export async function GET() {
  const sold = parseInt(await redisGet("founder:slots:sold") || "0", 10);
  return Response.json({ sold, available: Math.max(0, FOUNDER.slots - sold), soldOut: sold >= FOUNDER.slots });
}
