import { ReactNode } from "react";

export default function PageHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-end justify-between gap-4">
      <div>
        <h1 className="flex items-center font-display text-xl font-bold tracking-wide text-slate-100">
          <span className="mr-2 inline-block h-5 w-1 rounded bg-gradient-to-b from-tide-300 to-tide-600" />
          {title}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
