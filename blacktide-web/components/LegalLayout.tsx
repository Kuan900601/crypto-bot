import Link from "next/link";
import { ArrowLeft } from "lucide-react";
export default function LegalLayout({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl pb-6">
      <Link href="/" className="mb-4 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-tide-300"><ArrowLeft size={13} /> 返回首頁</Link>
      <h1 className="font-display text-2xl font-bold text-gold">{title}</h1>
      <div className="mt-1 text-xs text-slate-500">最後更新：{updated}</div>
      <div className="hairline-gold my-5" />
      <div className="space-y-5">{children}</div>
    </div>
  );
}
export function Clause({ title, children }: { title: string; children: React.ReactNode }) {
  return (<section><h2 className="text-[15px] font-semibold text-slate-100">{title}</h2><div className="mt-1.5 text-sm leading-relaxed text-slate-400">{children}</div></section>);
}
