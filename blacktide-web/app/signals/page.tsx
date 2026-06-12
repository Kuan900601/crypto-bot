"use client";

import { useState } from "react";
import { useFetch } from "@/lib/useFetch";
import { SignalsResponse, Direction } from "@/lib/types";
import SignalCard from "@/components/SignalCard";
import PageHeader from "@/components/PageHeader";
import { SourceBadge } from "@/components/Badges";

type Tab = "active" | "history";
type DirFilter = "all" | Direction;

export default function SignalsPage() {
  const { data } = useFetch<SignalsResponse>("/api/signals", 15000);
  const [tab, setTab] = useState<Tab>("active");
  const [dir, setDir] = useState<DirFilter>("all");

  const list = (tab === "active" ? data?.active : data?.history) ?? [];
  const filtered = dir === "all" ? list : list.filter((s) => s.direction === dir);

  return (
    <div>
      <PageHeader
        title="信號 Signals"
        subtitle="追蹤中為 active_signals，歷史為 signal_results（分段加權結算）"
        right={data && <SourceBadge source={data.source} error={data.error} />}
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg bg-ink-800 p-1">
          {(["active", "history"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={
                "rounded-md px-3 py-1.5 text-sm transition " +
                (tab === t ? "bg-tide-500/20 text-tide-300" : "text-slate-400 hover:text-slate-200")
              }
            >
              {t === "active" ? `追蹤中 ${data?.active.length ?? 0}` : `歷史 ${data?.history.length ?? 0}`}
            </button>
          ))}
        </div>
        <div className="flex rounded-lg bg-ink-800 p-1">
          {(["all", "long", "short"] as DirFilter[]).map((d) => (
            <button
              key={d}
              onClick={() => setDir(d)}
              className={
                "rounded-md px-3 py-1.5 text-sm transition " +
                (dir === d ? "bg-ink-600 text-slate-100" : "text-slate-400 hover:text-slate-200")
              }
            >
              {d === "all" ? "全部" : d === "long" ? "多" : "空"}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="card p-10 text-center text-sm text-slate-500">沒有符合條件的信號</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((s) => (
            <SignalCard key={s.id} s={s} />
          ))}
        </div>
      )}
    </div>
  );
}
