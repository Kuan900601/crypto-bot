import { entryGradeDisplay } from "@/lib/format";
import { Direction, Tier, EntryGrade } from "@/lib/types";

export function DirBadge({ d }: { d: Direction }) {
  const long = d === "long";
  return (
    <span
      className={
        "inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold " +
        (long ? "bg-up/15 text-up" : "bg-down/15 text-down")
      }
    >
      {long ? "多 LONG" : "空 SHORT"}
    </span>
  );
}

export function TierBadge({ t }: { t: Tier }) {
  const map: Record<Tier, string> = {
    S: "bg-tide-500/20 text-tide-300 ring-tide-500/40",
    A: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
    B: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
    C: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
  };
  return <span className={"inline-flex rounded-md px-1.5 py-0.5 text-[11px] font-bold ring-1 " + map[t]}>Tier {t}</span>;
}

// 進場品質：顯示中文，但保留內部值在 title（不更動內部值）
export function GradeBadge({ g }: { g: EntryGrade }) {
  const high = g === "S" || g === "A";
  const mid = g === "B" || g === "C";
  const cls = high
    ? "bg-tide-500/15 text-tide-300"
    : mid
    ? "bg-slate-500/15 text-slate-300"
    : "bg-down/10 text-down/80";
  return (
    <span className={"inline-flex rounded-md px-1.5 py-0.5 text-[11px] " + cls} title={`entry_grade=${g}`}>
      {entryGradeDisplay(g)}
    </span>
  );
}

export function SourceBadge({ source, error }: { source: string; error?: string }) {
  const live = source === "live";
  const cls = live
    ? "bg-up/15 text-up ring-up/30"
    : source === "error"
    ? "bg-down/15 text-down ring-down/30"
    : "bg-amber-500/15 text-amber-300 ring-amber-500/30";
  const label = live ? "LIVE · Redis" : source === "error" ? "離線 · 模擬" : "DEMO · 模擬資料";
  return (
    <span className={"inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 " + cls} title={error || ""}>
      <span className={"h-1.5 w-1.5 rounded-full " + (live ? "bg-up pulse-dot" : source === "error" ? "bg-down" : "bg-amber-400")} />
      {label}
    </span>
  );
}
