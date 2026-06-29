import { ReactNode } from "react";
import { RefreshCw } from "lucide-react";
export function Card({ className = "", children, onClick }: { className?: string; children?: ReactNode; onClick?: () => void }) {
  return (
    <div onClick={onClick}
      className={`rounded-2xl border border-white/[0.07] bg-ink-800/55 shadow-[inset_0_1px_0_rgba(255,255,255,0.04),0_8px_30px_rgba(0,0,0,0.35)] ${className}`}>
      {children}
    </div>
  );
}
export function SectionTitle({ title, desc, right }: { title: string; desc?: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-3">
      <div>
        <h1 className="text-lg font-bold tracking-wide">{title}</h1>
        {desc && <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{desc}</p>}
      </div>
      {right}
    </div>
  );
}
type Tone = "up" | "down" | "tide" | "slate" | "amber";
const TONES: Record<Tone, string> = {
  up: "bg-up/10 text-up border-up/20",
  down: "bg-down/10 text-down border-down/20",
  tide: "bg-tide-500/10 text-tide-300 border-tide-500/20",
  slate: "bg-white/5 text-slate-300 border-white/10",
  amber: "bg-amber-500/10 text-amber-300 border-amber-500/20",
};
export function Badge({ tone = "slate", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${TONES[tone]}`}>{children}</span>;
}
export function Progress({ value, tone = "tide" }: { value: number; tone?: "tide" | "up" | "down" | "amber" }) {
  const colors = { tide: "bg-tide-400", up: "bg-up", down: "bg-down", amber: "bg-amber-400" };
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
      <div className={`h-full rounded-full transition-all duration-500 ${colors[tone]}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}
export function Chip({ active, onClick, children }: { active?: boolean; onClick?: () => void; children: ReactNode }) {
  return (
    <button onClick={onClick} className={`rounded-full border px-3 py-1 text-xs transition-all ${active ? "border-tide-500/45 bg-tide-500/15 text-tide-300" : "border-white/10 text-slate-400 hover:bg-white/5"}`}>
      {children}
    </button>
  );
}
export function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "up" | "down" }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`mt-1 font-mono text-xl font-bold ${tone === "up" ? "text-up" : tone === "down" ? "text-down" : ""}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-slate-500">{sub}</div>}
    </Card>
  );
}

/** 骨架屏基本元件：取代灰塊 animate-pulse，貼合實際內容形狀用。
 *  .skeleton 動畫遵守 prefers-reduced-motion（見 globals.css）。 */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-lg ${className}`} />;
}

/** 通用骨架卡片：模擬「圖示 + 標題列 + N 行內容」的卡片形狀，給信號卡/行情卡共用。 */
export function SkeletonCard({ lines = 2 }: { lines?: number }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="ml-auto h-4 w-12" />
      </div>
      <div className="mt-3 space-y-2">
        {Array.from({ length: lines }).map((_, i) => <Skeleton key={i} className="h-3 w-full" />)}
      </div>
    </Card>
  );
}

/** 空狀態元件：取代純文字「沒有符合條件的事件」，依情境給圖示 + 標題 + 說明 + 可選行動按鈕。 */
export function EmptyState({ icon, title, desc, action }: { icon?: ReactNode; title: string; desc?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-white/5 px-6 py-12 text-center">
      {icon && <div className="mb-1 text-slate-600">{icon}</div>}
      <div className="text-sm font-medium text-slate-400">{title}</div>
      {desc && <div className="max-w-xs text-xs leading-relaxed text-slate-600">{desc}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/** 配合 usePullToRefresh 用的視覺指示器：下拉時跟著手指距離淡入/旋轉，放開達門檻後轉成載入中。
 *  只渲染圖示，不含手勢邏輯——手勢邏輯都在 hook 裡，這裡單純顯示用。 */
export function PullIndicator({ pullDistance, refreshing, threshold }: { pullDistance: number; refreshing: boolean; threshold: number }) {
  if (!refreshing && pullDistance <= 0) return null;
  const ready = pullDistance >= threshold;
  const height = refreshing ? 40 : Math.min(pullDistance, 40);
  return (
    <div className="flex items-center justify-center overflow-hidden" style={{ height, transition: refreshing ? "height .2s ease-out" : undefined }}>
      <RefreshCw size={16} className={`text-tide-300 ${refreshing || ready ? "ptr-spinner" : ""}`} style={{ opacity: refreshing ? 1 : Math.min(1, pullDistance / threshold) }} />
    </div>
  );
}
