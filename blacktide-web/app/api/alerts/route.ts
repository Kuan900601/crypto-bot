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

export async function GET() {
  try {
    const [events, liqRaw] = await Promise.all([
      redisLRange("at:events", -50, -1),
      redisGet("at:liquidations"),
    ]);
    let liqRecords: any[] = [];
    if (liqRaw) {
      try { liqRecords = JSON.parse(liqRaw)?.records ?? []; } catch {}
    }
    if (events.length || liqRecords.length) {
      const evtAlerts = events.slice().reverse().map(mapEvent);
      const liqAlerts = liqRecords.slice(-20).reverse().map(mapLiquidation).filter(Boolean) as AlertItem[];
      return Response.json({ alerts: [...liqAlerts, ...evtAlerts], source: "redis" });
    }
  } catch {}
  return Response.json({ alerts: ALERTS, source: "mock" });
}
