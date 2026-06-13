import { COINS, BYBIT_REST } from "@/lib/bybit";
export const dynamic = "force-dynamic";
const cache = new Map<string, { ts: number; bars: unknown[] }>();
const OK = new Set(["15", "60", "240", "D"]);
export async function GET(req: Request) {
  const u = new URL(req.url);
  const symbol = u.searchParams.get("symbol") || "BTCUSDT";
  const interval = u.searchParams.get("interval") || "60";
  const cfg = COINS.find((c) => c.bybit === symbol);
  if (!cfg || !OK.has(interval)) return Response.json({ bars: [] }, { status: 400 });
  const key = symbol + ":" + interval;
  const hit = cache.get(key);
  if (hit && Date.now() - hit.ts < 30000) return Response.json({ bars: hit.bars });
  try {
    const r = await fetch(`${BYBIT_REST}/v5/market/kline?category=linear&symbol=${symbol}&interval=${interval}&limit=200`, { cache: "no-store" });
    const d = await r.json();
    const bars = (d.result.list as string[][]).map((b) => ({
      time: Math.floor(+b[0] / 1000),
      open: +b[1] / cfg.div, high: +b[2] / cfg.div, low: +b[3] / cfg.div, close: +b[4] / cfg.div,
      volume: +b[5],
    })).reverse();
    cache.set(key, { ts: Date.now(), bars });
    return Response.json({ bars });
  } catch {
    return Response.json({ bars: [] });
  }
}
