import { Signal } from "@/lib/types";
import { fmtPrice, fmtPct, timeAgoZh } from "@/lib/format";
import { DirBadge, TierBadge, GradeBadge } from "./Badges";

function EntryText({ s }: { s: Signal }) {
  if (s.entryLow && s.entryHigh && s.entryLow !== s.entryHigh) {
    return <>{fmtPrice(s.entryLow)} – {fmtPrice(s.entryHigh)}</>;
  }
  return <>{fmtPrice(s.entryLow || s.entryHigh)}</>;
}

export default function SignalCard({ s }: { s: Signal }) {
  const closed = s.status === "closed";
  const win = (s.finalPct ?? 0) > 0;
  return (
    <div className="card p-4 transition hover:glow">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-slate-100">{s.symbol}</span>
          <DirBadge d={s.direction} />
        </div>
        <div className="flex items-center gap-1.5">
          <TierBadge t={s.tier} />
          <GradeBadge g={s.entryGrade} />
        </div>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
        <div>
          <div className="text-[10px] text-slate-500">進場</div>
          <div className="font-mono text-slate-200"><EntryText s={s} /></div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500">止損</div>
          <div className="font-mono text-down">{fmtPrice(s.stopLoss)}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500">盈虧比</div>
          <div className="font-mono text-slate-200">{s.rr ? s.rr.toFixed(2) + "R" : "—"}</div>
        </div>
      </div>

      {s.tps.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {s.tps.map((t) => (
            <span
              key={t.level}
              className={
                "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[11px] " +
                (t.hit ? "bg-up/15 text-up ring-1 ring-up/30" : "bg-ink-700 text-slate-400")
              }
              title={`權重 ${t.weight}% · ${t.r}R`}
            >
              {t.hit ? "✓" : ""}TP{t.level} {fmtPrice(t.price)}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-ink-700 pt-2 text-xs text-slate-500">
        <span>{s.score ? "評分 " + s.score : ""}{s.votes ? " · " + s.votes + " 票" : ""}{s.newsVote !== 0 ? " · 新聞" + (s.newsVote > 0 ? "+1" : "-1") : ""}</span>
        {closed ? (
          <span className={"font-mono font-semibold " + (win ? "text-up" : "text-down")}>
            {fmtPct(s.finalPct ?? 0)} <span className="text-slate-600">{s.note}</span>
          </span>
        ) : (
          <span>{timeAgoZh(s.openedAt)}</span>
        )}
      </div>
    </div>
  );
}
