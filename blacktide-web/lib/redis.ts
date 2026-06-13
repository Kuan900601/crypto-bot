const BASE = process.env.UPSTASH_REDIS_REST_URL;
const TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN;

export async function redisGet(key: string): Promise<string | null> {
  if (!BASE || !TOKEN) return null;
  try {
    const r = await fetch(`${BASE}/get/${encodeURIComponent(key)}`, {
      headers: { Authorization: `Bearer ${TOKEN}` }, cache: "no-store",
    });
    if (!r.ok) return null;
    const j = await r.json();
    return typeof j.result === "string" ? j.result : null;
  } catch { return null; }
}

export async function redisSet(key: string, value: string): Promise<boolean> {
  if (!BASE || !TOKEN) return false;
  try {
    const r = await fetch(BASE, {
      method: "POST",
      headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify(["SET", key, value]), cache: "no-store",
    });
    if (!r.ok) return false;
    const j = await r.json();
    return j.result === "OK";
  } catch { return false; }
}
