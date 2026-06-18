export const dynamic = "force-dynamic";
import { redisCmd } from "@/lib/redis";

function todayKey() {
  return new Date().toISOString().slice(0, 10); // YYYY-MM-DD UTC
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { type, path, duration } = body ?? {};
    if (type === "pv") {
      const date = todayKey();
      await Promise.allSettled([
        redisCmd(["INCR", "web:pv:total"]),
        redisCmd(["INCR", "web:pv:daily:" + date]),
        path ? redisCmd(["ZINCRBY", "web:pv:pages", "1", String(path).slice(0, 80)]) : Promise.resolve(),
      ]);
    } else if (type === "session" && typeof duration === "number" && duration >= 3 && duration <= 7200) {
      await Promise.allSettled([
        redisCmd(["LPUSH", "web:session:durations", String(Math.round(duration))]),
        redisCmd(["LTRIM", "web:session:durations", "0", "2999"]),
      ]);
    }
    return new Response(null, { status: 204 });
  } catch {
    return new Response(null, { status: 204 }); // always silent
  }
}

export async function GET() {
  try {
    const today = todayKey();
    const days14: string[] = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10);
      days14.push(d);
    }
    const [totalRaw, todayRaw, durationsRaw, ...dailyRaws] = await Promise.all([
      redisCmd(["GET", "web:pv:total"]),
      redisCmd(["GET", "web:pv:daily:" + today]),
      redisCmd(["LRANGE", "web:session:durations", "0", "999"]),
      ...days14.map((d) => redisCmd(["GET", "web:pv:daily:" + d])),
    ]);
    const durations = Array.isArray(durationsRaw) ? durationsRaw.map(Number).filter((n) => n > 0) : [];
    const avgSession = durations.length ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : 0;
    const pvByDay = days14.map((d, i) => ({ date: d.slice(5), count: Number(dailyRaws[i]) || 0 }));
    const yesterdayKey = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    const yesterdayCount = pvByDay.find((x) => x.date === yesterdayKey.slice(5))?.count ?? 0;
    return Response.json({
      totalPV: Number(totalRaw) || 0,
      todayPV: Number(todayRaw) || 0,
      yesterdayPV: yesterdayCount,
      avgSessionSec: avgSession,
      sampleCount: durations.length,
      pvByDay,
    });
  } catch {
    return Response.json({ totalPV: 0, todayPV: 0, yesterdayPV: 0, avgSessionSec: 0, sampleCount: 0, pvByDay: [] });
  }
}
