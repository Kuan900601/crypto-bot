"use client";
import { useState } from "react";
import { SectionTitle, Card } from "@/components/ui";
import { Smartphone, Bell, Search, Crown, Gift, BrainCircuit, Radio, ShieldAlert, ChevronDown, BookOpen, RefreshCw, Repeat2, Zap } from "lucide-react";
import { C } from "@/lib/theme";
import Corner from "@/components/site/Corner";
const SECTIONS = [
  {
    icon: Smartphone, title: "把網站加到手機主畫面（像 App 一樣）",
    body: (
      <div className="space-y-2">
        <p className="font-semibold text-slate-200">iPhone / iPad（Safari）</p>
        <ol className="ml-4 list-decimal space-y-1 text-slate-400">
          <li>用 <b>Safari</b> 開啟 kuroshioweb.vercel.app</li>
          <li>點下方中間的「分享」圖示（方框加向上箭頭）</li>
          <li>下滑選「<b>加入主畫面</b>」→ 右上角「新增」</li>
          <li>桌面就會出現黑潮圖示，點開是全螢幕、像 App</li>
        </ol>
        <p className="mt-2 font-semibold text-slate-200">Android（Chrome）</p>
        <ol className="ml-4 list-decimal space-y-1 text-slate-400">
          <li>用 <b>Chrome</b> 開啟網站</li>
          <li>右上角「⋮」選單 →「<b>加到主畫面</b> / 安裝應用程式」</li>
          <li>確認後桌面出現圖示</li>
        </ol>
      </div>
    ),
  },
  {
    icon: Bell, title: "開啟推播通知 / 設定夜間勿擾",
    body: (
      <div className="space-y-1 text-slate-400">
        <p>到「<b>會員中心 → 推播通知</b>」把開關打開，就能在有新訊號或重要提醒時收到通知。</p>
        <p>不想被半夜吵到？勾選「<b>夜間勿擾</b>」並設定起訖時間（例如 23:00–08:00），這段時間就不會推播。</p>
      </div>
    ),
  },
  {
    icon: Search, title: "搜尋任何幣種 / 美股看即時圖表 + AI 分析",
    body: (
      <div className="space-y-1 text-slate-400">
        <p>點頂部搜尋框，輸入代號（例如 <b>BTC、SOL、NVDA</b>），點結果即可看到：</p>
        <ul className="ml-4 list-disc space-y-1">
          <li>即時報價、24h 高低量、資金費率</li>
          <li><b>AI 即時分析</b>：RSI、趨勢、ATR、MA20/50、支撐壓力與操作參考</li>
          <li>互動式 K 線圖（可切換週期）</li>
        </ul>
      </div>
    ),
  },
  {
    icon: Crown, title: "方案差異：免費 / Plus / Pro",
    body: (
      <div className="space-y-1 text-slate-400">
        <p><b className="text-slate-200">免費</b>：市場總覽、基本行情。</p>
        <p><b className="text-tide-300">Plus</b>：解鎖 AI 分析、新聞中心、異常監控。</p>
        <p><b className="text-amber-300">Pro</b>：在 Plus 之上再解鎖黑潮船長訊號與策略回測。</p>
        <p className="mt-1">可在任一鎖住的頁面點「查看方案」或會員中心升級，支援加密貨幣付款，年繳更省。</p>
      </div>
    ),
  },
  {
    icon: Gift, title: "邀請好友拿免費訂閱",
    body: (
      <div className="space-y-1 text-slate-400">
        <p>到「<b>活動</b>」頁複製你的專屬 UID 或邀請連結分享給朋友。</p>
        <p>朋友註冊時填入你的 UID（用連結會自動帶入），<b>每成功邀請 5 人，免費送 1 個月 Plus</b>，可重複累積。</p>
      </div>
    ),
  },
  {
    icon: BrainCircuit, title: "看懂 AI 分析的指標",
    body: (
      <div className="space-y-1 text-slate-400">
        <ul className="ml-4 list-disc space-y-1">
          <li><b>RSI(14)</b>：&gt;70 偏超買、&lt;30 偏超賣，中間為中性。</li>
          <li><b>趨勢</b>：價 &gt; MA20 &gt; MA50 為多頭排列，反之空頭。</li>
          <li><b>ATR</b>：波動大小，越高代表振幅越大、要控好倉位。</li>
          <li><b>支撐 / 壓力</b>：近期低點 / 高點，常見的進出參考價位。</li>
          <li><b>信心 / 風險</b>：綜合分數，僅供參考，非保證。</li>
        </ul>
      </div>
    ),
  },
  {
    icon: Radio, title: "黑潮船長訊號怎麼看",
    body: (
      <div className="space-y-1 text-slate-400">
        <p>每則訊號附有方向（做多/做空）、進場區、<b>三段止盈（40/35/25）</b>與動態止損。點開卡片可看完整計畫。</p>
        <p>訊號是「紀律 + 機率篩選」，不是穩賺。請依自身風險承受度，做好部位與資金管理。</p>
      </div>
    ),
  },
  {
    icon: RefreshCw, title: "信號多久更新一次？",
    body: (
      <div className="space-y-1 text-slate-400">
        <p>系統<b className="text-slate-200">全天候不間斷</b>掃描，但不是固定時間推訊號——而是「條件符合才出手」。每則訊號出現前需通過：</p>
        <ul className="ml-4 list-disc space-y-1">
          <li>7+1 策略投票達門檻（至少兩票）</li>
          <li>五維評分（趨勢/動能/結構/量能/風險）全部通過</li>
          <li>盈虧比 ≥ 最低要求</li>
          <li>非「連敗保護模式」暫停期</li>
        </ul>
        <p className="mt-1">實際頻率視市況而定，行情清晰時每日 1–4 則；震盪低品質時可能整天無訊號，這是保護機制，非系統異常。</p>
      </div>
    ),
  },
  {
    icon: Repeat2, title: "可以自動跟單（複製交易）嗎？",
    body: (
      <div className="space-y-1 text-slate-400">
        <p>目前<b className="text-slate-200">不支援自動跟單</b>。黑潮是「訊號服務」——每則信號附有進場區、三段止盈（40/35/25）與動態止損，需要你自行在交易所下單執行。</p>
        <p>這樣設計的原因：</p>
        <ul className="ml-4 list-disc space-y-1">
          <li>每位交易者的倉位大小、風險承受度不同，不適合統一資金管理</li>
          <li>讓你完整理解每筆交易邏輯，培養自己的判斷力而非盲目跟單</li>
          <li>避免網路延遲或滑點造成與系統不同的成交結果</li>
        </ul>
        <p className="mt-1">建議先用小倉位跟蹤幾週、熟悉信號風格後再放大。</p>
      </div>
    ),
  },
  {
    icon: Zap, title: "AI 到底怎麼分析幣種？",
    body: (
      <div className="space-y-1 text-slate-400">
        <p>黑潮不是「問 ChatGPT 看不看好」，而是一套基於市場數據的<b className="text-slate-200">多策略投票系統</b>：</p>
        <ol className="ml-4 list-decimal space-y-1">
          <li><b>7 大技術策略</b>各自獨立投票：趨勢追隨、動量、量價、均線排列、支撐阻力、BOS 突破、訂單流</li>
          <li><b>新聞情緒（第 8 票）</b>：即時掃描相關新聞，判斷正面/負面/中性加入投票</li>
          <li><b>五維評分</b>：趨勢強度、動能質量、結構完整性、量能確認、整體風險</li>
          <li><b>硬門檻過濾</b>：盈虧比未達要求，不論分數多高都不出訊號</li>
        </ol>
        <p className="mt-1">首頁的「AI 觀點 · BTC」是根據即時 K 線與指標即時計算的技術偏向，非語言模型的文字預測。</p>
      </div>
    ),
  },
  {
    icon: ShieldAlert, title: "風險與免責",
    body: (
      <div className="space-y-1 text-slate-400">
        <p>本平台提供的所有資訊均為市場資訊與教育用途，<b>不構成投資建議、不保證獲利</b>。加密貨幣交易具高度風險。</p>
        <p>請僅以可承受損失的閒置資金參與，並自負交易結果。詳見側欄「風險揭露聲明」。</p>
      </div>
    ),
  },
];
export default function GuidePage() {
  const [open, setOpen] = useState<number>(0);
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <SectionTitle title="使用教學" desc="幾分鐘上手黑潮 BLACKTIDE，把它變成你的交易儀表板" right={<BookOpen size={18} className="text-tide-300" />} />
      <div className="space-y-3">
        {SECTIONS.map((sec, i) => {
          const Icon = sec.icon;
          const isOpen = open === i;
          return (
            <Card key={i} className="relative overflow-hidden p-0">
              {isOpen && <Corner pos="tr" />}
              <button onClick={() => setOpen(isOpen ? -1 : i)} className="flex w-full items-center gap-3 px-4 py-3.5 text-left">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" style={{ background: "rgba(0,212,255,0.1)", color: C.primary }}><Icon size={17} /></span>
                <span className="flex-1 text-sm font-semibold">{sec.title}</span>
                <ChevronDown size={16} className={"shrink-0 text-slate-500 transition-transform " + (isOpen ? "rotate-180" : "")} />
              </button>
              {isOpen && <div className="border-t border-white/5 px-4 py-3.5 text-xs leading-relaxed">{sec.body}</div>}
            </Card>
          );
        })}
      </div>
      <Card className="p-4 text-center text-xs text-slate-500">還有問題？到「會員中心 → 意見反饋」告訴我們。</Card>
    </div>
  );
}
