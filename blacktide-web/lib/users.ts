import bcrypt from "bcryptjs";
import { redisGetKey, redisSetKey } from "./redis";

// 網站會員資料層。存在 Upstash Redis，key 前綴 web:user:*，與 bot 的 bot_data 完全隔離（不污染交易資料）。
// 沒設 Redis 時退回記憶體 Map（僅供本機開發，重啟即清空）。

export type Plan = "free" | "premium";

export interface WebUser {
  email: string;
  name: string;
  hash?: string; // credentials 才有；Google 登入無密碼
  plan: Plan;
  planExpiry?: string; // ISO；過期視為 free
  isAdmin: boolean;
  provider: "credentials" | "google";
  createdAt: string;
}

const mem = new Map<string, WebUser>();
const KEY = (email: string) => "web:user:" + email.trim().toLowerCase();
const isAdminEmail = (email: string) =>
  email.trim().toLowerCase() === (process.env.ADMIN_EMAIL || "").trim().toLowerCase() &&
  !!process.env.ADMIN_EMAIL;

export async function getUser(email: string): Promise<WebUser | null> {
  const k = KEY(email);
  const raw = await redisGetKey(k);
  if (raw) {
    try { return JSON.parse(raw) as WebUser; } catch { return null; }
  }
  return mem.get(k) ?? null;
}

export async function putUser(u: WebUser): Promise<void> {
  const k = KEY(u.email);
  const ok = await redisSetKey(k, JSON.stringify(u));
  if (!ok) mem.set(k, u);
}

export async function createUser(email: string, name: string, password: string): Promise<WebUser> {
  const clean = email.trim().toLowerCase();
  if (await getUser(clean)) throw new Error("EMAIL_TAKEN");
  const u: WebUser = {
    email: clean,
    name: (name || "").trim() || clean.split("@")[0],
    hash: await bcrypt.hash(password, 10),
    plan: "free",
    isAdmin: isAdminEmail(clean),
    provider: "credentials",
    createdAt: new Date().toISOString(),
  };
  await putUser(u);
  return u;
}

// Google 首次登入時，確保有一筆 user 紀錄（沒密碼）
export async function ensureOAuthUser(email: string, name?: string): Promise<WebUser> {
  const existing = await getUser(email);
  if (existing) return existing;
  const clean = email.trim().toLowerCase();
  const u: WebUser = {
    email: clean,
    name: (name || "").trim() || clean.split("@")[0],
    plan: "free",
    isAdmin: isAdminEmail(clean),
    provider: "google",
    createdAt: new Date().toISOString(),
  };
  await putUser(u);
  return u;
}

export async function verifyUser(email: string, password: string): Promise<WebUser | null> {
  const u = await getUser(email);
  if (!u || !u.hash) return null;
  return (await bcrypt.compare(password, u.hash)) ? u : null;
}

export function isPremiumActive(u: WebUser | null): boolean {
  if (!u) return false;
  if (u.isAdmin) return true;
  if (u.plan !== "premium") return false;
  if (u.planExpiry && new Date(u.planExpiry).getTime() < Date.now()) return false;
  return true;
}

// 付款成功後升級（自到期日或現在起 +days，可累加續訂）
export async function upgradeUser(email: string, days = 30): Promise<void> {
  const u = await getUser(email);
  if (!u) return;
  const now = Date.now();
  const base = u.planExpiry && new Date(u.planExpiry).getTime() > now ? new Date(u.planExpiry).getTime() : now;
  u.plan = "premium";
  u.planExpiry = new Date(base + days * 86_400_000).toISOString();
  await putUser(u);
}
