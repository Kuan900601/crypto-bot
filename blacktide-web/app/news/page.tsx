"use client";
import { useEffect, useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";
import { NewsItem } from "@/lib/types";
import { SectionTitle, Card, Badge, Chip, Skeleton, EmptyState } from "@/components/ui";
import { Newspaper } from "lucide-react";
import { C } from "@/lib/theme";
import Corner from "@/components/site/Corner";
const SENT: Record<NewsItem["sentiment"], { label: string; tone: "up" | "down" | "slate" }> = {
  bull: { label: "利多", tone: "up" }, bear: { label: "利空", tone: "down" }, neutral: { label: "中性", tone: "slate" },
};
function hrefOf(n: NewsItem): string {
  if (n.url && /^https?:\/\//.test(n.url)) return n.url;
  return "https://www.google.com/search?q=" + encodeURIComponent(n.title);
}
export default function NewsPage() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [src, setSrc] = useState("");
  const [f, setF] = useState<"all" | NewsItem["sentiment"]>("all");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch("/api/news").then((r) => r.json()).then((d) => { setNews(d.news || []); setSrc(d.source || ""); }).catch(() => {}).finally(() => setLoading(false));
  }, []);
  const filtered = useMemo(() => news.filter((n) =>
    (f === "all" || n.sentiment === f) &&
    (!q || (n.title + n.summary + n.tags.join("")).toLowerCase().includes(q.toLowerCase()))
  ), [news, f, q]);
  const srcLabel = src === "bot" ? "Bot 新聞模組（即時）" : src === "rss" ? "RSS 即時中文新聞" : src === "cryptopanic" ? "CryptoPanic（即時）" : "展示資料";
  return (
    <div className="space-y-5">
      <SectionTitle title="即時新聞" desc={"情緒分析 + 影響評估 · 來源：" + srcLabel} />
      <div className="flex flex-wrap items-center gap-2">
        <Chip active={f === "all"} onClick={() => setF("all")}>全部</Chip>
        <Chip active={f === "bull"} onClick={() => setF("bull")}>利多</Chip>
        <Chip active={f === "bear"} onClick={() => setF("bear")}>利空</Chip>
        <Chip active={f === "neutral"} onClick={() => setF("neutral")}>中性</Chip>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜尋新聞…"
          className="ml-auto w-40 rounded-lg border border-white/5 bg-ink-800 px-3 py-1.5 text-sm outline-none focus:border-tide-500/40" />
      </div>
      <div className="space-y-3">
        {loading && [0, 1, 2].map((i) => (
          <Card key={i} className="p-4">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="mt-2 h-4 w-3/4" />
            <Skeleton className="mt-2 h-3 w-1/2" />
          </Card>
        ))}
        {!loading && filtered.length === 0 && (
          <EmptyState icon={<Newspaper size={22} />} title="沒有符合條件的新聞" desc="換個分類或搜尋關鍵字試試。" />
        )}
        {!loading && filtered.map((n) => (
          <a key={n.id} href={hrefOf(n)} target="_blank" rel="noreferrer" className="block">
            <Card className="sigrow relative overflow-hidden p-4 transition hover:border-tide-500/30 hover:bg-white/[0.03]">
              <span className="accent-bar" style={{ background: `linear-gradient(${SENT[n.sentiment].tone === "up" ? C.green : SENT[n.sentiment].tone === "down" ? C.rose : C.dim},transparent)` }} />
              <div className="row-sweep" />
              <Corner pos="tr" />
              {/* 第一行：badge + 標題 */}
              <div className="flex items-start gap-2" style={{ position: "relative", zIndex: 1 }}>
                <Badge tone={SENT[n.sentiment].tone}>{SENT[n.sentiment].label}</Badge>
                <h3 className="min-w-0 flex-1 text-sm font-semibold leading-snug line-clamp-2">{n.title}</h3>
                <ExternalLink size={13} className="mt-0.5 shrink-0 text-slate-600" />
              </div>
              {/* 摘要 */}
              {n.summary && n.summary !== "（點擊閱讀原文）" && (
                <p className="mt-2 text-xs leading-relaxed text-slate-400 line-clamp-2">{n.summary}</p>
              )}
              {/* 底部：來源 + 影響 + 標籤 + 時間 */}
              <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                <span className="shrink-0">{n.source}</span>
                <span className="flex items-center gap-0.5 shrink-0">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <span key={i} className={`h-1.5 w-1.5 rounded-full ${i < n.impact ? "bg-tide-400" : "bg-white/10"}`} />
                  ))}
                </span>
                <span className="flex flex-wrap gap-1">
                  {n.tags.slice(0, 3).map((t) => (
                    <span key={t} className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-400">{t}</span>
                  ))}
                </span>
                <span className="ml-auto shrink-0">{n.time}</span>
              </div>
            </Card>
          </a>
        ))}
      </div>
    </div>
  );
}
