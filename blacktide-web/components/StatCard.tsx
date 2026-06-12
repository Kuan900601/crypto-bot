import { ReactNode } from "react";

interface Props {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "up" | "down" | "neutral";
}

export default function StatCard({ label, value, sub, tone = "neutral" }: Props) {
  const valColor =
    tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-slate-100";
  return (
    <div className="card p-4">
      <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={"mt-1 font-mono text-2xl font-semibold " + valColor}>{value}</div>
      {sub != null && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}
