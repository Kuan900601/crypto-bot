import { ReactNode } from "react";

export function Card({ className = "", children, onClick }: { className?: string; children?: ReactNode; onClick?: () => void }) {
  return (
    <div onClick={onClick}
      className={`rounded-xl border border-white/[0.07] bg-gradient-to-b from-white/[0.05] to-white/[0.01] ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({ title, desc, right }: { title: string; desc?: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-3">
      <div>
        <h1 className="font-display text-lg font-bold tracking-wide">
          <span className="mr-2 inline-block h-4 w-1 rounded bg-gradient-to-b from-tide-300 to-tide-600 align-middle" />
          {title}
        </h1>
        {desc && <p className="mt-1 text-xs text-slate-500">{desc}</p>}
      </div>
      {right}
    </div>
  );
}

type Tone = "up" | "down" | "tide" | "slate" | "amber";
const TONES: Record<Tone, string> = {
  up: "bg-up/10 text-up border-up/20",
  down: "bg-down/10 text-down border-down/20",
  tide: "bg-tide-500/10 text-tide-300 border-tide-500/25",
  slate: "bg-white/5 text-slate-300 border-white/10",
  amber: "bg-amber-500/10 text-amber-300 border-amber-500/20",
};
export function Badge({ tone = "slate", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${TONES[tone]}`}>{children}</span>;
}

export function Progress({ value, tone = "tide" }: { value: number; tone?: "tide" | "up" | "down" | "amber" }) {
  const colors = { tide: "bg-tide-400", up: "bg-up", down: "bg-down", amber: "bg-amber-400" };
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
      <div className={`h-full rounded-full ${colors[tone]}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}

export function Chip({ active, onClick, children }: { active?: boolean; onClick?: () => void; children: ReactNode }) {
  return (
    <button onClick={onClick}
      className={`shrink-0 rounded-full border px-3 py-1 text-xs transition-colors ${active ? "border-tide-500/45 bg-tide-500/15 text-tide-300" : "border-white/10 text-slate-400 hover:bg-white/5"}`}>
      {children}
    </button>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "up" | "down" }) {
  return (
    <Card className="p-3.5 md:p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`mt-1 font-mono text-lg font-bold md:text-xl ${tone === "up" ? "text-up" : tone === "down" ? "text-down" : ""}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-slate-500">{sub}</div>}
    </Card>
  );
}
