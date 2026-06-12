import { Signal, SignalStats, TakeProfit, Direction, Tier, EntryGrade } from "./types";

// 結算權重固定（與 bot 一致，P0 不可動）：TP1=15% TP2=35% TP3=35% TP4=15%
const WEIGHTS = [15, 35, 35, 15];
// TP 階梯 R 倍數（CLAUDE.md 第 8 節）：1.5 / 2.5 / 3.5 / 5.0
const RMULT = [1.5, 2.5, 3.5, 5.0];

function num(v: unknown, d = 0): number {
  const n = Number(v);
  return isFinite(n) ? n : d;
}
function dir(d: unknown): Direction {
  return String(d ?? "").toUpperCase() === "SHORT" ? "short" : "long";
}
function tier(t: unknown): Tier {
  const v = String(t ?? "C").toUpperCase();
  return (["S", "A", "B", "C"].includes(v) ? v : "C") as Tier;
}
function grade(g: unknown): EntryGrade {
  const v = String(g ?? "C").toUpperCase();
  return (["S", "A", "B", "C", "D"].includes(v) ? v : "C") as EntryGrade;
}

// active_signals 的 key 是 "BTC/USDT_LONG" 之類；value 不一定有 symbol → 從 key 還原
function parseSymbol(key: string, sig: Record<string, unknown>): string {
  const raw = sig.symbol ? String(sig.symbol) : key.replace(/_(LONG|SHORT)$/i, "");
  return raw.replace(/[/:].*$/, ""); // 去掉 /USDT、:USDT 等後綴
}

function buildTps(sig: Record<string, unknown>): TakeProfit[] {
  const rawHit = sig.tp_hit;
  const hit: number[] = Array.isArray(rawHit) ? rawHit.map((x) => Number(x)) : [];
  const out: TakeProfit[] = [];
  for (let i = 0; i < 4; i++) {
    const price = num(sig["tp" + (i + 1)]);
    if (!price) continue;
    out.push({ level: i + 1, price, r: RMULT[i], weight: WEIGHTS[i], hit: hit.includes(i + 1) });
  }
  return out;
}

export function mapActiveSignals(active: Record<string, unknown>): Signal[] {
  const entries = Object.entries(active || {});
  return entries
    .map(([key, raw]) => {
      const sig = (raw ?? {}) as Record<string, unknown>;
      const tps = buildTps(sig);
      const d = dir(sig.direction);
      const anyHit = tps.some((t) => t.hit);
      return {
        id: key,
        symbol: parseSymbol(key, sig),
        direction: d,
        tier: tier(sig.tier),
        entryGrade: grade(sig.entry_grade),
        score: num(sig.score),
        votes: num(sig.consensus_at_entry),
        newsVote: (sig.news_vote_at_entry ? (d === "long" ? 1 : -1) : 0) as -1 | 0 | 1,
        entryLow: num(sig.entry),
        entryHigh: num(sig.entry),
        stopLoss: num(sig.sl),
        tps,
        leverage: 15,
        winRate: 0,
        rr: num(sig.rr_at_entry),
        status: anyHit ? "tp" : "active",
        openedAt: String(sig.created ?? ""),
      } as Signal;
    })
    .sort((a, b) => Date.parse(b.openedAt) - Date.parse(a.openedAt));
}

export function mapResults(results: unknown[]): Signal[] {
  const arr = Array.isArray(results) ? results : [];
  return arr
    .slice()
    .reverse()
    .map((raw, i) => {
      const r = (raw ?? {}) as Record<string, unknown>;
      const d = dir(r.direction);
      const fp = num(r.final_pct);
      return {
        id: String(r.symbol ?? "") + "_" + String(r.closed_at ?? i),
        symbol: String(r.symbol ?? "").replace(/[/:].*$/, ""),
        direction: d,
        tier: tier(r.tier),
        entryGrade: grade(r.entry_grade),
        score: num(r.score),
        votes: num(r.consensus_at_entry),
        newsVote: (r.news_vote_at_entry ? (d === "long" ? 1 : -1) : 0) as -1 | 0 | 1,
        entryLow: num(r.entry),
        entryHigh: num(r.entry),
        stopLoss: num(r.sl_at_entry),
        tps: [],
        leverage: 15,
        winRate: 0,
        rr: num(r.rr_at_entry),
        status: "closed",
        finalPct: fp,
        openedAt: String(r.closed_at ?? ""),
        note: String(r.result ?? ""),
      } as Signal;
    });
}

// 與 bot /edge 同精神：勝率、Wilson 95% 下界、平均盈虧、毛 EV、最大連虧
export function computeStats(results: unknown[]): SignalStats {
  const arr = Array.isArray(results) ? results : [];
  const n = arr.length;
  if (!n) return { n: 0, winRate: 0, ev: 0, avgWin: 0, avgLoss: 0, maxLossStreak: 0, wilsonLb: 0 };

  const pcts = arr.map((r) => num((r as Record<string, unknown>).final_pct));
  const wins = pcts.filter((p) => p > 0);
  const losses = pcts.filter((p) => p <= 0);
  const winRate = (wins.length / n) * 100;
  const avgWin = wins.length ? wins.reduce((a, b) => a + b, 0) / wins.length : 0;
  const avgLoss = losses.length ? losses.reduce((a, b) => a + b, 0) / losses.length : 0;
  const ev = pcts.reduce((a, b) => a + b, 0) / n;

  // 最大連續虧損
  let cur = 0;
  let maxLossStreak = 0;
  for (const p of pcts) {
    if (p <= 0) {
      cur += 1;
      maxLossStreak = Math.max(maxLossStreak, cur);
    } else cur = 0;
  }

  // Wilson 95% 下界
  const z = 1.96;
  const phat = wins.length / n;
  const denom = 1 + (z * z) / n;
  const center = phat + (z * z) / (2 * n);
  const margin = z * Math.sqrt((phat * (1 - phat)) / n + (z * z) / (4 * n * n));
  const wilsonLb = ((center - margin) / denom) * 100;

  return { n, winRate, ev, avgWin, avgLoss, maxLossStreak, wilsonLb };
}
