const BASE = process.env.UPSTASH_REDIS_REST_URL;
const TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN;
async function call(body: unknown): Promise<{ result: unknown } | null> {
  if (!BASE || !TOKEN) return null;
  try {
    const r = await fetch(BASE, {
      method: "POST",
      headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify(body), cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as { result: unknown };
  } catch { return null; }
}
// 通用：傳入指令陣列，回傳 result（字串 / 陣列 / 數字 / null）
export async function redisCmd(args: (string | number)[]): Promise<unknown> {
  const j = await call(args);
  return j ? j.result : null;
}
export async function redisGet(key: string): Promise<string | null> {
  const v = await redisCmd(["GET", key]);
  return typeof v === "string" ? v : null;
}
export async function redisSet(key: string, value: string): Promise<boolean> {
  const v = await redisCmd(["SET", key, value]);
  return v === "OK";
}
export async function redisSAdd(key: string, member: string): Promise<void> { await redisCmd(["SADD", key, member]); }
export async function redisSMembers(key: string): Promise<string[]> {
  const v = await redisCmd(["SMEMBERS", key]);
  return Array.isArray(v) ? (v as string[]) : [];
}
export async function redisLPush(key: string, value: string): Promise<void> { await redisCmd(["LPUSH", key, value]); }
export async function redisLRange(key: string, start: number, stop: number): Promise<string[]> {
  const v = await redisCmd(["LRANGE", key, start, stop]);
  return Array.isArray(v) ? (v as string[]) : [];
}
