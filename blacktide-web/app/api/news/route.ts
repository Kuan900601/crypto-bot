import { NextResponse } from "next/server";
import { NEWS } from "@/lib/mock";
import { NewsItem } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

// 真實新聞：設了 CRYPTOPANIC_TOKEN 才抓 CryptoPanic，否則靜默退回 mock（與 bot 新聞模組同精神）。
// 注意：情緒/影響力為「投票/熱度」的粗略對映，非 analyzer 的新聞分析，僅展示用。

interface CPResult {
  id: number | string; title: string; published_at: string; url: string;
  source?: { title?: string; domain?: string };
  votes?: { positive?: number; negative?: number; important?: number };
  currencies?: { code: string }[];
}

function mapSentiment(v?: CPResult["votes"]): NewsItem["sentiment"] {
  const pos = v?.positive ?? 0, neg = v?.negative ?? 0;
  if (pos > neg + 1) return "bull";
  if (neg > pos + 1) return "bear";
  return "neutral";
}

function mapImpact(v?: CPResult["votes"]): NewsItem["impact"] {
  const score = (v?.important ?? 0) + (v?.positive ?? 0) + (v?.negative ?? 0);
  const clamped = Math.min(5, Math.max(1, Math.round(score / 3) || 1));
  return clamped as NewsItem["impact"];
}

export async function GET() {
  const token = process.env.CRYPTOPANIC_TOKEN;
  if (!token) return NextResponse.json({ news: NEWS, source: "mock" });

  try {
    const r = await fetch(
      `https://cryptopanic.com/api/v1/posts/?auth_token=${token}&public=true&kind=news`,
      { cache: "no-store" }
    );
    if (!r.ok) return NextResponse.json({ news: NEWS, source: "mock" });
    const j = await r.json();
    const results: CPResult[] = j?.results ?? [];
    const news: NewsItem[] = results.slice(0, 30).map((p) => ({
      id: String(p.id),
      title: p.title,
      source: p.source?.title || p.source?.domain || "CryptoPanic",
      time: p.published_at,
      sentiment: mapSentiment(p.votes),
      impact: mapImpact(p.votes),
      summary: "",
      tags: (p.currencies || []).map((c) => c.code).slice(0, 6),
    }));
    return NextResponse.json({ news: news.length ? news : NEWS, source: news.length ? "cryptopanic" : "mock" });
  } catch {
    return NextResponse.json({ news: NEWS, source: "mock" });
  }
}
