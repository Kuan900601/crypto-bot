"use client";
import { useState } from "react";
import { ChevronDown, HelpCircle, RefreshCw, Repeat2, Zap, Shield, DollarSign, Clock, TrendingUp, Lock, Bell } from "lucide-react";
import { C, SERIF } from "@/lib/theme";

interface Item { q: string; a: string; icon: typeof HelpCircle }
const SECTIONS: { title: string; items: Item[] }[] = [
  {
    title: "信號與策略",
    items: [
      {
        icon: RefreshCw,
        q: "黑潮信號多久出現一次？",
        a: "沒有固定頻率。黑潮採用 7+1 策略投票機制，只有當市場出現高品質機會（五維評分、盈虧比同時達標）才發送信號。一天可能 0～5 筆，刻意避免「為出信號而出」。質量優先，不追求數量。",
      },
      {
        icon: TrendingUp,
        q: "黑潮的策略是什麼？勝率多少？",
        a: "黑潮整合 7 大技術策略（趨勢追隨、動量、BOS 突破、均線排列、支撐阻力、訂單流、新聞情緒）進行投票，加上 AI 新聞分析。只有多項策略同時達成共識、五維評分達標、RR ≥ 1.5 才觸發信號。每筆信號均附帶入場品質等級（S/A/B/C）。歷史績效以 Telegram 公開記錄為準，可自行查閱。",
      },
      {
        icon: Clock,
        q: "信號出現後多久需要執行？",
        a: "信號附有建議入場區間，超過一定時間或價格偏離過多時，黑潮系統會自動標示信號過期（預設 10 分鐘）。建議在信號發出後盡快確認，錯過入場窗口的信號不建議追入。",
      },
    ],
  },
  {
    title: "跟單與使用",
    items: [
      {
        icon: Repeat2,
        q: "我可以直接跟單操作嗎？",
        a: "黑潮信號提供技術分析參考，不構成投資建議。每筆信號均附有入場、止損、三段止盈（40/35/25 權重），你可以參考這些數值自行決策。我們不提供自動跟單服務，所有交易決策由你自行負責。",
      },
      {
        icon: Shield,
        q: "信號的止損設定是否合理？",
        a: "黑潮止損以 ATR 波動率自適應計算，避免止損過緊被洗出或過寬虧損過大。止損距離通常介於 1.5%～3.5% 之間，視當前市場波動度而定。三段止盈設計讓你在趨勢延伸時保留倉位，同時鎖定早期利潤。",
      },
      {
        icon: Bell,
        q: "如何不錯過信號？",
        a: "訂閱 Telegram 頻道 @KuroshioSignal 是最直接的方式，信號即時推送且有歷史記錄可查。Pro 會員還可透過本平台的信號頁面查看詳細進出場邏輯與 AI 分析報告。",
      },
    ],
  },
  {
    title: "AI 分析",
    items: [
      {
        icon: Zap,
        q: "AI 分析是怎麼運作的？",
        a: "每次分析呼叫 Bybit API 取得近期 K 線數據，計算 RSI、MA20/MA50、ATR、24h 動能、資金費率、未平倉量 OI，搭配市場恐貪指數與新聞情緒，由模型綜合這些技術指標輸出偏多/偏空/中性判斷、信心分數、支撐壓力位，以及文字版操作建議。屬於技術指標輔助工具，不是預測未來。",
      },
      {
        icon: HelpCircle,
        q: "AI 分析的準確度有多高？",
        a: "AI 分析基於技術指標統計，無法預測突發消息或流動性衝擊。「偏多」不代表一定上漲，「信心 80%」是指標一致性高、不是成功率。請將 AI 分析作為輔助參考，與自身判斷結合使用。",
      },
    ],
  },
  {
    title: "訂閱與付費",
    items: [
      {
        icon: DollarSign,
        q: "Plus 和 Pro 有什麼差別？",
        a: "Plus 解鎖 AI 分析、新聞中心、異常監控與全站圖表功能。Pro 在 Plus 基礎上加入黑潮船長信號（含詳細進出場邏輯）與策略回測工具。免費版可瀏覽市場總覽與部分基礎功能。",
      },
      {
        icon: Lock,
        q: "付費方式支援哪些？",
        a: "目前透過 NOWPayments 接受加密貨幣付款，包括 USDT、BTC、ETH 等主流幣種。訂閱方案分月繳與年繳，年繳方案更划算。付款後系統自動開通，無需手動審核。",
      },
    ],
  },
];

function AccordionItem({ item }: { item: Item }) {
  const [open, setOpen] = useState(false);
  const Icon = item.icon;
  return (
    <div className="border-b border-white/5 last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-start gap-3 py-4 text-left transition-colors hover:text-slate-200"
      >
        <Icon size={15} className="mt-0.5 shrink-0" style={{ color: C.primary2 }} />
        <span className="flex-1 text-sm font-medium text-slate-200">{item.q}</span>
        <ChevronDown size={15} className={`mt-0.5 shrink-0 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="pb-4 pl-6 pr-2 text-sm leading-relaxed text-slate-400">
          {item.a}
        </div>
      )}
    </div>
  );
}

export default function FaqPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="accent-text" style={{ fontFamily: SERIF, fontSize: 24, fontWeight: 700 }}>常見問題</h1>
        <p className="mt-1" style={{ fontSize: 13, color: C.mut }}>關於黑潮信號、AI 分析、訂閱方案的常見疑問解答</p>
      </div>
      {SECTIONS.map((s) => (
        <div key={s.title} className="rounded-xl px-4" style={{ border: `1px solid ${C.line}`, background: "rgba(255,255,255,0.02)" }}>
          <div className="border-b border-white/5 py-3" style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.5, color: C.dim, textTransform: "uppercase" }}>{s.title}</div>
          {s.items.map((item) => <AccordionItem key={item.q} item={item} />)}
        </div>
      ))}
    </div>
  );
}
