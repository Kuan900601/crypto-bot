"use client";

import { useFetch } from "@/lib/useFetch";
import { NewsItem } from "@/lib/types";
import { timeAgoZh } from "@/lib/format";
import PageHeader from "@/components/PageHeader";

interface Resp { news: NewsItem[] }

function sentMeta(s: NewsItem["sentiment"]) {
  if (s === "bull") return { txt: "看多", cls: "bg-up/15 text-up" };
  if (s === "bear") return { txt: "看空", cls: "bg-down/15 text-down" };
  return { txt: "中性", cls: "bg-slate-500/15 text-slate-300" };
}

export default function NewsPage() {
  const { data } = useFetch<Resp>("/api/news", 30000);
  const news = data?.news ?? [];
  return (
    <div>
      <PageHeader title="情報 News" subtitle="新聞情緒（Mock）· bot 第 8 票來源，驗證通過後可接 CryptoPanic + Claude 分析" right={<span className="text-[11px] text-slate-600">Mock</span>} />
      <div className="space-y-3">
        {news.map((n) => {
          const m = sentMeta(n.sentiment);
          return (
            <div key={n.id} className="card p-4">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-sm font-medium text-slate-100">{n.title}</h3>
                <span className={"shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-semibold " + m.cls}>{m.txt}</span>
              </div>
              <p className="mt-1.5 text-sm text-slate-400">{n.summary}</p>
              <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-500">
                <span>{n.source}</span>
                <span>·</span>
                <span>{timeAgoZh(n.time)}</span>
                <span>·</span>
                <span className="text-amber-400">影響 {"●".repeat(n.impact)}{"○".repeat(5 - n.impact)}</span>
                <div className="ml-auto flex gap-1">
                  {n.tags.map((t) => (
                    <span key={t} className="rounded bg-ink-700 px-1.5 py-0.5 text-slate-400">{t}</span>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
