import { NEWS as MOCK } from "@/lib/mock";
import { redisGet } from "@/lib/redis";
import { NewsItem } from "@/lib/types";
export const dynamic = "force-dynamic";
let cache: { ts: number; body: unknown } | null = null;
function clampImpact(n: number): NewsItem["impact"] {
  return Math.max(1, Math.min(5, Math.round(n))) as NewsItem["impact"];
}
/* eslint-disable @typescript-eslint/no-explicit-any */
function mapPost(raw: Record<string, any>, i: number): NewsItem | null {
  try {
    if (!raw?.title) return null;
    const v = raw.votes || {};
    const pos = +(v.positive ?? 0), neg = +(v.negative ?? 0), imp = +(v.important ?? 0);
    const sentiment: NewsItem["sentiment"] = pos > neg ? "bull" : neg > pos ? "bear" : "neutral";
    const t = raw.published_at ? new Date(raw.published_at) : null;
    return {
      id: String(raw.id ?? "cp-" + i),
      title: String(raw.title),
      source: String(raw.source?.title ?? raw.source?.domain ?? raw.domain ?? "CryptoPanic"),
      time: t ? t.toLocaleString("zh-TW", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "",
      sentiment,
      impact: clampImpact(1 + imp + Math.min(2, Math.floor((pos + neg) / 5))),
      summary: String(raw.description ?? raw.metadata?.description ?? "（來源僅提供標題。接上 bot 新聞分析後顯示摘要）"),
      tags: Array.isArray(raw.currencies) ? raw.currencies.slice(0, 4).map((c: any) => String(c.code)) : [],
      url: String(raw.url ?? raw.source?.url ?? ""),
    };
  } catch { return null; }
}
export async function GET() {
  if (cache && Date.now() - cache.ts < 120000) return Response.json(cache.body);
  try {
    const raw = await redisGet("web:news:analyzed");
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr) && arr.length) {
        const body = { news: arr.slice(0, 30), source: "bot" };
        cache = { ts: Date.now(), body };
        return Response.json(body);
      }
    }
  } catch {}
  const token = process.env.CRYPTOPANIC_TOKEN;
  if (token) {
    try {
      const base = process.env.CRYPTOPANIC_API_BASE || "https://cryptopanic.com/api/v1/posts/";
      const r = await fetch(`${base}?auth_token=${token}&public=true&kind=news`, { cache: "no-store" });
      if (r.ok) {
        const d = await r.json();
        const news = (Array.isArray(d.results) ? d.results : []).map(mapPost).filter(Boolean) as NewsItem[];
        if (news.length) {
          const body = { news, source: "cryptopanic" };
          cache = { ts: Date.now(), body };
          return Response.json(body);
        }
      }
    } catch {}
  }
  return Response.json({ news: MOCK, source: "mock" });
}
