"use client";
import { useEffect, useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";
import { NewsItem } from "@/lib/types";
import { SectionTitle, Card, Badge, Chip } from "@/components/ui";
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
  useEffect(() => {
    fetch("/api/news").then((r) => r.json()).then((d) => { setNews(d.news || []); setSrc(d.source || ""); }).catch(() => {});
  }, []);
  const filtered = useMemo(() => news.filter((n) =>
    (f === "all" || n.sentiment === f) &&
    (!q || (n.title + n.summary + n.tags.join("")).toLowerCase().includes(q.toLowerCase()))
  ), [news, f, q]);
  const srcLabel = src === "bot" ? "來源：bot 新聞模組（即時）" : src === "cryptopanic" ? "來源：CryptoPanic（即時）" : "來源：展示資料";
  return (
    <div className="space-y-5">
      <SectionTitle title="即時新聞" desc={"情緒分析 + 影響評估 · 點卡片看原文 · " + srcLabel} />
      <div className="flex flex-wrap items-center gap-2">
        <Chip active={f === "all"} onClick={() => setF("all")}>全部</Chip>
        <Chip active={f === "bull"} onClick={() => setF("bull")}>利多</Chip>
        <Chip active={f === "bear"} onClick={() => setF("bear")}>利空</Chip>
        <Chip active={f === "neutral"} onClick={() => setF("neutral")}>中性</Chip>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜尋新聞…"
          className="ml-auto w-40 rounded-lg border border-white/5 bg-ink-800 px-3 py-1.5 text-sm outline-none focus:border-tide-500/40" />
      </div>
      <div className="space-y-3">
        {filtered.length === 0 && <div className="rounded-xl border border-white/5 p-8 text-center text-sm text-slate-500">沒有符合條件的新聞</div>}
        {filtered.map((n) => (
          <a key={n.id} href={hrefOf(n)} target="_blank" rel="noreferrer" className="block">
            <Card className="p-4 transition hover:border-tide-500/30 hover:bg-white/[0.03]">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={SENT[n.sentiment].tone}>{SENT[n.sentiment].label}</Badge>
                <span className="text-sm font-semibold leading-snug">{n.title}</span>
                <span className="ml-auto flex shrink-0 items-center gap-1 text-[11px] text-slate-500">
                  {n.source} · {n.time} <ExternalLink size={12} className="text-slate-600" />
                </span>
              </div>
              {n.summary && <p className="mt-2 text-xs leading-relaxed text-slate-400">{n.summary}</p>}
              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <span className="text-[10px] text-slate-500">影響程度</span>
                <span className="flex gap-0.5">
                  {[0, 1, 2, 3, 4].map((i) => <span key={i} className={`h-1.5 w-1.5 rounded-full ${i < n.impact ? "bg-tide-400" : "bg-white/10"}`} />)}
                </span>
                <span className="ml-auto flex flex-wrap gap-1.5">
                  {n.tags.map((t) => <span key={t} className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-400">{t}</span>)}
                </span>
              </div>
            </Card>
          </a>
        ))}
      </div>
    </div>
  );
}
