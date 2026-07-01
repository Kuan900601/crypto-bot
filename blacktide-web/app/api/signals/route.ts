import { getServerSession } from "next-auth";
import { authOptions, getUser, tierOf } from "@/lib/auth";
import { SIGNALS } from "@/lib/mock";
import { redisGet } from "@/lib/redis";
import { Signal, TakeProfit } from "@/lib/types";
export const dynamic = "force-dynamic";
// free 等級只能拿到「方向 + 結果」，看不到任何操作價位（entry/sl/tp/leverage/rr）
type PublicSignal = Pick<Signal, "id" | "symbol" | "direction" | "tier" | "entryGrade" | "score" | "votes" | "newsVote" | "winRate" | "status" | "finalPct" | "openedAt" | "note"> & { tpHitCount: number; locked: true };
function sanitizeSignal(sig: Signal, tier: "free" | "air" | "pro"): Signal | PublicSignal {
  if (tier !== "free") return sig;
  return {
    id: sig?.id, symbol: sig?.symbol, direction: sig?.direction,
    tier: sig?.tier, entryGrade: sig?.entryGrade,
    score: sig?.score, votes: sig?.votes, newsVote: sig?.newsVote,
    winRate: sig?.winRate, status: sig?.status, finalPct: sig?.finalPct,
    openedAt: sig?.openedAt, note: sig?.note,
    tpHitCount: (sig?.tps ?? []).filter((t) => t?.hit).length,
    locked: true,
  };
}
const TP_WEIGHT: Record<number, number> = { 1: 40, 2: 35, 3: 25 };
/* eslint-disable @typescript-eslint/no-explicit-any */
function buildTps(raw: any, entry: number): TakeProfit[] {
  const hit: number[] = Array.isArray(raw?.tp_hit) ? raw.tp_hit : [];
  const out: TakeProfit[] = [];
  for (const lv of [1, 2, 3]) {
    const price = Number(raw?.["tp" + lv] ?? 0);
    if (!price) continue;
    const sl = Number(raw?.sl ?? 0);
    const risk = Math.abs(entry - sl) || 1;
    const r = +(Math.abs(price - entry) / risk).toFixed(1);
    out.push({ level: lv, price, r, weight: TP_WEIGHT[lv] ?? 0, hit: hit.includes(lv) });
  }
  return out;
}
function mapActive(symbol: string, raw: any): Signal | null {
  try {
    const entry = Number(raw?.entry ?? 0);
    if (!entry) return null;
    const dirStr = String(raw?.direction ?? raw?.direction_en ?? "LONG").toUpperCase();
    const isLong = !(dirStr.includes("SHORT") || dirStr.includes("空"));
    return {
      id: "active-" + symbol,
      symbol: symbol.replace("/USDT", "").replace("USDT", ""),
      direction: isLong ? "long" : "short",
      tier: (raw?.tier ?? "B") as Signal["tier"],
      entryGrade: (raw?.entry_grade ?? "C") as Signal["entryGrade"],
      score: Number(raw?.score ?? 0),
      votes: Number(raw?.votes ?? raw?.consensus_at_entry ?? raw?.consensus_votes ?? 0),
      newsVote: (raw?.news_vote ?? 0) as Signal["newsVote"],
      entryLow: entry, entryHigh: entry,
      stopLoss: Number(raw?.sl ?? 0),
      tps: buildTps(raw, entry),
      leverage: Number(raw?.leverage ?? 1),
      winRate: Number(raw?.win_rate ?? 0),
      rr: Number(raw?.rr ?? raw?.rr_at_entry ?? 1.5),
      status: "active",
      openedAt: String(raw?.created ?? ""),
    };
  } catch { return null; }
}
function mapResult(raw: any, i: number): Signal | null {
  try {
    if (!raw?.symbol) return null;
    const entry = Number(raw?.entry ?? 0);
    const finalPct = Number(raw?.final_pct ?? 0);
    const dirStr = String(raw?.direction ?? "LONG").toUpperCase();
    const isLong = !(dirStr.includes("SHORT") || dirStr.includes("空"));
    return {
      id: "hist-" + i,
      symbol: String(raw.symbol).replace("/USDT", "").replace("USDT", ""),
      direction: isLong ? "long" : "short",
      tier: (raw?.tier ?? "B") as Signal["tier"],
      entryGrade: (raw?.entry_grade ?? "C") as Signal["entryGrade"],
      score: Number(raw?.score ?? 0),
      votes: Number(raw?.votes ?? 0),
      newsVote: (raw?.news_vote ?? 0) as Signal["newsVote"],
      entryLow: entry, entryHigh: entry,
      stopLoss: Number(raw?.sl ?? 0),
      tps: buildTps(raw, entry),
      leverage: Number(raw?.leverage ?? 1),
      winRate: Number(raw?.win_rate ?? 0),
      rr: Number(raw?.rr ?? 1.5),
      status: finalPct > 0 ? "tp" : "sl",
      finalPct: +finalPct.toFixed(2),
      openedAt: String(raw?.created ?? raw?.closed_at ?? ""),
    };
  } catch { return null; }
}
export async function GET() {
  let tier: "free" | "air" | "pro" = "free";
  try {
    const session = await getServerSession(authOptions);
    const email = session?.user?.email;
    const u = email ? await getUser(email) : null;
    tier = tierOf(u);
  } catch {}

  const key = process.env.BOT_REDIS_KEY || "bot_data";
  const rawStr = await redisGet(key);
  if (rawStr) {
    try {
      const data = JSON.parse(rawStr);
      const out: Signal[] = [];
      // bot 實際寫小寫鍵 active_signals / signal_results；同時相容大寫
      const act = data?.active_signals ?? data?.ACTIVE_SIGNALS;
      if (act && typeof act === "object") {
        const actSignals: Signal[] = [];
        for (const [sym, sig] of Object.entries(act)) {
          const m = mapActive(sym, sig);
          if (m) actSignals.push(m);
        }
        // Object.entries 是 bot 寫入順序（最舊的先），不是新到舊——
        // 首頁的「今日信號預覽卡」只取第一個 status==="active" 的當預覽，
        // 沒排序的話永遠抓到最舊的進行中信號，新信號補的 win_rate 等欄位看起來像沒生效。
        // NaN-safe sort：openedAt 缺失的舊信號排到最末，避免成為首頁 previewSignal
        actSignals.sort((a, b) => (new Date(b.openedAt).getTime() || 0) - (new Date(a.openedAt).getTime() || 0));
        out.push(...actSignals);
      }
      const hist = data?.signal_results ?? data?.SIGNAL_RESULTS;
      if (Array.isArray(hist)) {
        hist.slice(-30).reverse().forEach((r: any, i: number) => {
          const m = mapResult(r, i);
          if (m) out.push(m);
        });
      }
      if (out.length) return Response.json({ signals: out.map((s) => sanitizeSignal(s, tier)), source: "redis" });
    } catch {}
  }
  return Response.json({ signals: SIGNALS.map((s) => sanitizeSignal(s, tier)), source: "mock" });
}
