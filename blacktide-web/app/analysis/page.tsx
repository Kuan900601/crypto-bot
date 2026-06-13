"use client";
import { ANALYSES } from "@/lib/mock";
import { SectionTitle, Card, Badge, Progress } from "@/components/ui";
import { fmtPrice } from "@/lib/format";
export default function AnalysisPage() {
  const avg = Math.round(ANALYSES.reduce((a, x) => a + x.sentiment, 0) / ANALYSES.length);
  return (
    <div className="space-y-5">
      <SectionTitle title="AI 智能分析" desc="多空判斷、信心指數與風險評分（DEMO 模擬資料）" />
      <Card className="p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold">市場綜合情緒</span>
          <span className="font-mono">{avg}/100</span>
        </div>
        <div className="mt-2"><Progress value={avg} tone={avg >= 55 ? "up" : avg <= 45 ? "down" : "tide"} /></div>
        <div className="mt-1.5 text-xs text-slate-500">{avg >= 55 ? "偏多" : avg <= 45 ? "偏空" : "中性"}</div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        {ANALYSES.map((a) => (
          <Card key={a.symbol} className="p-4">
            <div className="flex items-center gap-2">
              <span className="font-bold">{a.symbol}</span>
              <Badge tone={a.bias === "long" ? "up" : a.bias === "short" ? "down" : "slate"}>
                {a.bias === "long" ? "看多" : a.bias === "short" ? "看空" : "中性"}
              </Badge>
              <span className="ml-auto text-xs text-slate-500">風險評分 <span className={a.risk >= 60 ? "text-down" : "text-slate-300"}>{a.risk}</span></span>
            </div>
            <div className="mt-3 space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-14 shrink-0 text-slate-500">信心指數</span>
                <div className="flex-1"><Progress value={a.confidence} /></div>
                <span className="w-8 text-right font-mono">{a.confidence}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-14 shrink-0 text-slate-500">風險</span>
                <div className="flex-1"><Progress value={a.risk} tone={a.risk >= 60 ? "down" : "tide"} /></div>
                <span className="w-8 text-right font-mono">{a.risk}</span>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
              {a.support.map((v) => <span key={"s" + v} className="rounded bg-up/10 px-1.5 py-0.5 font-mono text-up">支 {fmtPrice(v)}</span>)}
              {a.resistance.map((v) => <span key={"r" + v} className="rounded bg-down/10 px-1.5 py-0.5 font-mono text-down">壓 {fmtPrice(v)}</span>)}
            </div>
            <div className="mt-3 rounded-lg bg-white/[0.03] p-2.5 text-xs leading-relaxed">
              <span className="font-semibold text-tide-300">建議：</span>{a.action}
            </div>
            <ul className="mt-2 space-y-1 text-[11px] text-slate-400">
              {a.basis.map((b, i) => <li key={i} className="flex gap-1.5"><span className="text-tide-500">·</span>{b}</li>)}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}
