import { NextResponse } from "next/server";
import { getBotData, REDIS_READY } from "@/lib/redis";
import { mapActiveSignals, mapResults, computeStats } from "@/lib/botMap";
import { DEMO_SIGNALS, DEMO_HISTORY, DEMO_STATS } from "@/lib/mock";
import { SignalsResponse } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function demo(extra?: Partial<SignalsResponse>): SignalsResponse {
  return { source: "demo", active: DEMO_SIGNALS, history: DEMO_HISTORY, stats: DEMO_STATS, ...extra };
}

export async function GET() {
  if (!REDIS_READY) {
    return NextResponse.json(demo());
  }
  try {
    const data = await getBotData();
    if (!data) {
      // Redis 通了但還沒有 bot_data（bot 尚未寫入）→ 退回 demo 但標明來源
      return NextResponse.json(demo({ source: "demo", error: "redis_empty" }));
    }
    const activeRaw = (data.active_signals ?? {}) as Record<string, unknown>;
    const resultsRaw = (data.signal_results ?? []) as unknown[];
    const payload: SignalsResponse = {
      source: "live",
      active: mapActiveSignals(activeRaw),
      history: mapResults(resultsRaw),
      stats: computeStats(resultsRaw),
    };
    return NextResponse.json(payload);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(demo({ source: "error", error: msg }));
  }
}
