// Upstash REST 讀取接縫。與 bot.py 同一機制：POST 到 base URL，命令採陣列格式 ["GET", key]。
// 沒設環境變數 → REDIS_READY=false，API 路由會自動退回 DEMO 模擬資料（與新聞模組同精神：缺 key 就靜默關閉）。
const URL = process.env.UPSTASH_REDIS_REST_URL;
const TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN;
const KEY = process.env.BOT_REDIS_KEY || "bot_data";

export const REDIS_READY: boolean = !!(URL && TOKEN);

export async function redisCmd(args: (string | number)[]): Promise<unknown> {
  if (!URL || !TOKEN) return null;
  const res = await fetch(URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(args),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`redis ${args[0]} HTTP ${res.status}`);
  const j = (await res.json()) as { result?: unknown; error?: string };
  if (j.error) throw new Error(String(j.error));
  return j.result ?? null;
}

// 唯讀：只 GET bot 寫好的整包狀態，從不寫入（不污染 bot 資料）
export async function getBotData(): Promise<Record<string, unknown> | null> {
  const raw = await redisCmd(["GET", KEY]);
  if (!raw || typeof raw !== "string") return null;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

// --- 一般 key 讀寫（給網站自己的會員資料用，key 前綴 web:*，與 bot 的 bot_data 完全隔離）---
export async function redisGetKey(key: string): Promise<string | null> {
  try {
    const r = await redisCmd(["GET", key]);
    return typeof r === "string" ? r : null;
  } catch {
    return null;
  }
}

export async function redisSetKey(key: string, value: string): Promise<boolean> {
  if (!REDIS_READY) return false;
  try {
    const r = await redisCmd(["SET", key, value]);
    return r === "OK";
  } catch {
    return false;
  }
}
