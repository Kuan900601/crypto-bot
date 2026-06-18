"use client";
import { useState } from "react";
import { Calendar, TrendingUp, DollarSign, Globe } from "lucide-react";

type Category = "all" | "crypto" | "macro" | "fed";

interface EventItem {
  date: string;
  title: string;
  desc: string;
  category: "crypto" | "macro" | "fed";
  impact: "high" | "medium";
}

const EVENTS: EventItem[] = [
  // 2025 重大事件（固定/週期性）
  { date: "每月第一個週五", title: "美國非農就業報告 NFP", desc: "美國每月勞工市場數據，超出預期通常帶動美元與股市波動。", category: "macro", impact: "high" },
  { date: "每月第二或第三週三", title: "美國 CPI 通膨數據", desc: "消費者物價指數，Fed 政策的核心依據，高於預期升息壓力上升。", category: "macro", impact: "high" },
  { date: "每月第二或第三週四", title: "美國 PPI 生產者物價", desc: "生產者物價指數，通膨先行指標。", category: "macro", impact: "medium" },
  { date: "每六週（約）", title: "FOMC 聯準會利率決策", desc: "聯準會利率決策會議，附隨 Powell 記者會與點陣圖。加息/降息/不動均影響市場流動性。", category: "fed", impact: "high" },
  { date: "每季一次（約 3 月、6 月、9 月、12 月）", title: "聯準會 SEP 經濟預測摘要", desc: "含點陣圖（Dot Plot），反映 FOMC 成員對未來利率路徑的預期。", category: "fed", impact: "high" },
  { date: "每年 8 月（Jackson Hole）", title: "Jackson Hole 全球央行年會", desc: "各國央行行長的政策信號場合，Powell 演講通常引發市場重定價。", category: "fed", impact: "high" },
  // 加密貨幣週期事件
  { date: "約每 4 年一次（下次 2028 年）", title: "比特幣減半事件 Halving", desc: "每 21 萬個區塊挖礦獎勵減半，供給衝擊歷史上均引發多頭週期。上次 2024-04-20。", category: "crypto", impact: "high" },
  { date: "每季", title: "ETH 生態重大升級（不定期）", desc: "以太坊核心協議升級，如 Pectra / Dencun，影響 Gas 費用與 Layer 2 成本結構。", category: "crypto", impact: "medium" },
  // 2025 年具體日期
  { date: "2025-01-20", title: "Trump 就職（已過）", desc: "美國新任總統就職，政策轉向訊號，含加密貨幣監管態度。", category: "macro", impact: "high" },
  { date: "2025-03-19", title: "FOMC 會議（3 月）", desc: "2025 年第二次聯準會利率決策，附 SEP 點陣圖與 Powell 記者會。", category: "fed", impact: "high" },
  { date: "2025-05-07", title: "FOMC 會議（5 月）", desc: "2025 年第三次聯準會利率決策。", category: "fed", impact: "high" },
  { date: "2025-06-18", title: "FOMC 會議（6 月）", desc: "2025 年第四次聯準會利率決策，附 SEP 點陣圖。今日。", category: "fed", impact: "high" },
  { date: "2025-07-30", title: "FOMC 會議（7 月）", desc: "2025 年第五次聯準會利率決策。", category: "fed", impact: "high" },
  { date: "2025-09-17", title: "FOMC 會議（9 月）", desc: "2025 年第六次聯準會利率決策，附 SEP 點陣圖。", category: "fed", impact: "high" },
  { date: "2025-10-29", title: "FOMC 會議（10 月）", desc: "2025 年第七次聯準會利率決策。", category: "fed", impact: "high" },
  { date: "2025-12-10", title: "FOMC 會議（12 月）", desc: "2025 年第八次聯準會利率決策，附 SEP 點陣圖，全年收尾。", category: "fed", impact: "high" },
];

const CATS: { key: Category; label: string; icon: typeof Calendar }[] = [
  { key: "all", label: "全部", icon: Calendar },
  { key: "crypto", label: "加密", icon: TrendingUp },
  { key: "macro", label: "總經", icon: Globe },
  { key: "fed", label: "Fed", icon: DollarSign },
];

const IMPACT_CLS = { high: "bg-down/20 text-down", medium: "bg-amber-500/20 text-amber-300" };
const CAT_CLS = { crypto: "bg-tide-500/15 text-tide-300", macro: "bg-blue-500/15 text-blue-300", fed: "bg-amber-500/15 text-amber-300" };
const CAT_LABEL = { crypto: "加密", macro: "總經", fed: "Fed" };

export default function CalendarPage() {
  const [cat, setCat] = useState<Category>("all");
  const filtered = cat === "all" ? EVENTS : EVENTS.filter((e) => e.category === cat);
  const high = filtered.filter((e) => e.impact === "high");
  const medium = filtered.filter((e) => e.impact === "medium");
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold">重要事件行事曆</h1>
        <p className="mt-1 text-sm text-slate-500">加密貨幣週期事件、美國總經數據、Fed 利率決策關鍵日期</p>
      </div>

      {/* 分類篩選 */}
      <div className="flex flex-wrap gap-2">
        {CATS.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setCat(key)}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${cat === key ? "bg-tide-500/20 text-tide-300" : "bg-white/[0.04] text-slate-400 hover:bg-white/[0.08]"}`}>
            <Icon size={12} />{label}
          </button>
        ))}
      </div>

      {/* 高影響事件 */}
      {high.length > 0 && (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-down" />
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">高影響事件</span>
          </div>
          <div className="space-y-2">
            {high.map((e, i) => (
              <div key={i} className="rounded-xl border border-white/5 bg-ink-800/60 p-4">
                <div className="flex flex-wrap items-start gap-2">
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-slate-100">{e.title}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${CAT_CLS[e.category]}`}>{CAT_LABEL[e.category]}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${IMPACT_CLS[e.impact]}`}>高影響</span>
                    </div>
                    <div className="mt-1 font-mono text-xs text-tide-400">{e.date}</div>
                    <div className="mt-1.5 text-xs leading-relaxed text-slate-400">{e.desc}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 中影響事件 */}
      {medium.length > 0 && (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">中影響事件</span>
          </div>
          <div className="space-y-2">
            {medium.map((e, i) => (
              <div key={i} className="rounded-xl border border-white/5 bg-ink-800/40 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-slate-200">{e.title}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${CAT_CLS[e.category]}`}>{CAT_LABEL[e.category]}</span>
                </div>
                <div className="mt-1 font-mono text-xs text-slate-500">{e.date}</div>
                <div className="mt-1.5 text-xs leading-relaxed text-slate-500">{e.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3 text-[11px] leading-relaxed text-slate-600">
        日期僅供參考，具體發布時間以美國財政部、勞工部、Fed 官方網站為準。本頁不構成投資建議。
      </div>
    </div>
  );
}
