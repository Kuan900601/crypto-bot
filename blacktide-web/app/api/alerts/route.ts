import { ALERTS } from "@/lib/mock";
import { redisGet, redisLRange } from "@/lib/redis";
import { AlertItem } from "@/lib/types";
export const dynamic = "force-dynamic";

/* eslint-disable @typescript-eslint/no-explicit-any */

// at:events 是 auto_trader.py push_event() 寫入的純文字列（RPUSH，新事件在尾端），
// 用 emoji 前綴粗略推斷嚴重度；本身沒有逐筆時間戳，只能保證新到舊排序，time 留空。
function severityOf(text: string): AlertItem["severity"] {
  if (text.includes("🔴")) return "critical";
  if (text.includes("⚠️") || text.includes("🪧") || text.includes("⏰") || text.includes("⏭")) return "warn";
  return "info";
}
function symbolOf(text: string): string | undefined {
  const seg = text.split("｜");
  for (const s of seg) {
    const m = s.trim().match(/^([A-Z]{2,10})(USDT)?$/);
    if (m) return m[1];
  }
  return undefined;
}
function mapEvent(text: string, i: number): AlertItem {
  const seg = text.split("｜");
  return {
    id: "evt-" + i + "-" + text.length,
    type: "system",
    severity: severityOf(text),
    title: (seg[0] || text).trim().slice(0, 60),
    detail: seg.length > 1 ? seg.slice(1).join("｜") : text,
    time: "",
    symbol: symbolOf(text),
  };
}

// at:liquidations 是這個 bot 自己帳戶的爆倉紀錄（ex.fetch_my_liquidations()），
// 不是市場面巨鯨/資金費率/巨量訊號——語意上對應 AlertItem 的 "liquidation" 類型最準確。
// ccxt 永續合約統一符號格式是 "AR/USDT:USDT"，原本只 replace("/USDT","")+replace("USDT","")
// 對這種格式會漏掉冒號後的 USDT，留下「AR:」這種尾巴——改成直接取「/」前面的底層資產代號。
function baseSymbol(raw: string): string {
  return String(raw).split("/")[0].split(":")[0];
}
function mapLiquidation(raw: any, i: number): AlertItem | null {
  if (!raw?.symbol) return null;
  let time = "";
  try { if (raw.time) time = new Date(raw.time).toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" }); } catch {}
  return {
    id: "liq-" + i,
    type: "liquidation",
    severity: "critical",
    title: "本帳戶爆倉：" + baseSymbol(raw.symbol),
    detail: "數量 " + (raw.amount ?? "未知"),
    time,
    symbol: baseSymbol(raw.symbol),
  };
}

function fmtUsd(n: number): string {
  if (n >= 1_000_000) return "$" + (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return "$" + (n / 1_000).toFixed(1) + "K";
  return "$" + n.toFixed(0);
}
function timeOf(iso?: string): string {
  try { return iso ? new Date(iso).toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" }) : ""; } catch { return ""; }
}

// market:liquidations / market:funding / market:volume 是 market_monitor.py（v65 新增的獨立模組，
// 訂閱 Bybit 公開 WS）寫的全市場資料，跟上面 at:liquidations（本帳戶）是不同性質。
function mapMarketLiquidation(text: string, i: number): AlertItem | null {
  try {
    const d = JSON.parse(text);
    const amount = Number(d.amount ?? 0);
    return {
      id: "mliq-" + i, type: "liquidation",
      severity: amount >= 200000 ? "critical" : "warn",
      // Bybit 官方定義：S="Buy" 代表多單被清算、"Sell" 代表空單被清算（v66 修正，原本標反）
      title: "全市場爆倉：" + d.symbol + " " + (d.side === "Buy" ? "多單爆倉" : "空單爆倉") + " " + fmtUsd(amount),
      detail: "數量 " + d.qty + " · 價格 " + d.price,
      time: timeOf(d.time), symbol: d.symbol,
    };
  } catch { return null; }
}
function mapMarketFunding(text: string, i: number): AlertItem | null {
  try {
    const d = JSON.parse(text);
    const pct = (Number(d.fundingRate ?? 0) * 100).toFixed(3);
    return {
      id: "mfund-" + i, type: "funding",
      severity: Math.abs(Number(d.fundingRate ?? 0)) >= 0.01 ? "critical" : "warn",
      title: d.symbol + " 資金費率異常：" + pct + "%",
      detail: Number(d.fundingRate) > 0 ? "多頭付費給空頭，多方擁擠" : "空頭付費給多頭，空方擁擠",
      time: timeOf(d.time), symbol: d.symbol,
    };
  } catch { return null; }
}
function mapMarketVolume(text: string, i: number): AlertItem | null {
  try {
    const d = JSON.parse(text);
    const total = Number(d.totalUsd ?? 0);
    return {
      id: "mvol-" + i, type: "volume",
      severity: total >= 10_000_000 ? "warn" : "info",
      title: d.symbol + " " + Math.round((d.windowSec ?? 300) / 60) + " 分鐘成交量異常：" + fmtUsd(total),
      detail: "窗口內累計成交額 " + fmtUsd(total),
      time: timeOf(d.time), symbol: d.symbol,
    };
  } catch { return null; }
}

export async function GET() {
  try {
    const [events, liqRaw, marketLiq, marketFunding, marketVolume, liqBuckets] = await Promise.all([
      redisLRange("at:events", -50, -1),
      redisGet("at:liquidations"),
      redisLRange("market:liquidations", -30, -1),
      redisLRange("market:funding", -60, -1),
      redisLRange("market:volume", -30, -1),
      redisLRange("market:liq_buckets", -1440, -1),
    ]);
    let liqRecords: any[] = [];
    if (liqRaw) {
      try { liqRecords = JSON.parse(liqRaw)?.records ?? []; } catch {}
    }
    const hasAny = events.length || liqRecords.length || marketLiq.length || marketFunding.length || marketVolume.length;
    if (hasAny) {
      // funding 依幣種去重：同一幣只留最新一筆，避免歷史殘留（如 MANTA 洗版時期）佔滿版面
      const fundingLatest = new Map<string, string>();
      for (const t of marketFunding) {
        try { const sym = JSON.parse(t)?.symbol; if (sym) fundingLatest.set(sym, t); } catch {}
      }
      const fundingDeduped = Array.from(fundingLatest.values());

      // 多/空爆倉匯總（market:liq_buckets 分鐘桶，bot 端 market_monitor 寫入；UTC 分鐘字串）
      const nowMs = Date.now();
      let long1h = 0, short1h = 0, long24h = 0, short24h = 0;
      for (const t of liqBuckets) {
        try {
          const b = JSON.parse(t);
          const age = nowMs - new Date(b.t + ":00Z").getTime();
          if (!(age >= 0 && age <= 24 * 3600_000)) continue;
          long24h += Number(b.longUsd ?? 0); short24h += Number(b.shortUsd ?? 0);
          if (age <= 3600_000) { long1h += Number(b.longUsd ?? 0); short1h += Number(b.shortUsd ?? 0); }
        } catch {}
      }
      const liqSummary = { long1h, short1h, long24h, short24h, hasData: liqBuckets.length > 0 };

      const evtAlerts = events.slice().reverse().map(mapEvent);
      const liqAlerts = liqRecords.slice(-20).reverse().map(mapLiquidation).filter(Boolean) as AlertItem[];
      const mLiqAlerts = marketLiq.slice().reverse().map(mapMarketLiquidation).filter(Boolean) as AlertItem[];
      const mFundAlerts = fundingDeduped.slice().reverse().map(mapMarketFunding).filter(Boolean) as AlertItem[];
      const mVolAlerts = marketVolume.slice().reverse().map(mapMarketVolume).filter(Boolean) as AlertItem[];
      return Response.json({
        alerts: [...mLiqAlerts, ...mFundAlerts, ...mVolAlerts, ...liqAlerts, ...evtAlerts],
        liqSummary,
        source: "redis",
      });
    }
  } catch {}
  return Response.json({ alerts: ALERTS, source: "mock" });
}
