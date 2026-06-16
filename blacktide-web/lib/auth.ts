import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import bcrypt from "bcryptjs";
import { redisGet, redisSet, redisSAdd } from "./redis";
export type Tier = "free" | "air" | "pro";
export interface WebUser {
  uid: string; email: string; nickname: string; name: string; phone?: string; avatar?: string; hash?: string;
  plan: "free" | "premium"; planExpiry?: string;
  tier: Tier; cycle?: "monthly" | "yearly"; subAmount?: number; subStartedAt?: string;
  emailVerified?: boolean; phoneVerified?: boolean;
  invitedBy?: string; referrals?: number; referralRewarded?: number;
  isAdmin: boolean; isLifetime: boolean; createdAt: string;
}
const mem = new Map<string, WebUser>();
const KEY = (email: string) => "web:user:" + email.trim().toLowerCase();
const UIDKEY = (uid: string) => "web:uid:" + uid.trim().toUpperCase();
export const USERS_SET = "web:users";
export async function getUser(email: string): Promise<WebUser | null> {
  const k = KEY(email);
  const raw = await redisGet(k);
  if (raw) { try { return JSON.parse(raw) as WebUser; } catch {} }
  return mem.get(k) ?? null;
}
export async function saveUser(u: WebUser): Promise<void> {
  const k = KEY(u.email);
  if (!u.nickname) u.nickname = u.name || u.email.split("@")[0];
  if (!u.name) u.name = u.nickname;
  const ok = await redisSet(k, JSON.stringify(u));
  if (!ok) mem.set(k, u);
  await redisSAdd(USERS_SET, u.email);
  await redisSet(UIDKEY(u.uid), u.email);
}
export async function getEmailByUid(uid: string): Promise<string | null> {
  if (!uid) return null;
  const e = await redisGet(UIDKEY(uid));
  if (e) return e;
  for (const u of Array.from(mem.values())) if (u.uid.toUpperCase() === uid.trim().toUpperCase()) return u.email;
  return null;
}
export function tierOf(u: { isAdmin?: boolean; isLifetime?: boolean; tier?: string; plan?: string; planExpiry?: string } | null | undefined): Tier {
  if (!u) return "free";
  if (u.isAdmin || u.isLifetime) return "pro";
  if (u.planExpiry && new Date(u.planExpiry).getTime() < Date.now()) return "free";
  if (u.tier === "air" || u.tier === "pro") return u.tier;
  if (u.plan === "premium") return "pro";
  return "free";
}
export function isPremium(u: { plan?: string; isLifetime?: boolean; tier?: string; planExpiry?: string } | null | undefined): boolean {
  return tierOf(u) !== "free";
}
// 累加式發放「N 個月 Plus(air)」：從現有未到期日往後加，free→升 air，pro 保持 pro
export function grantAirMonths(u: WebUser, months: number) {
  const now = Date.now();
  const base = u.planExpiry && new Date(u.planExpiry).getTime() > now ? new Date(u.planExpiry).getTime() : now;
  u.planExpiry = new Date(base + months * 30 * 86400000).toISOString();
  u.plan = "premium";
  if (u.tier !== "pro") u.tier = "air";
  if (!u.cycle) u.cycle = "monthly";
}
export function newUser(email: string, nickname: string, hash?: string, phone?: string, avatar?: string, invitedBy?: string): WebUser {
  const admin = !!process.env.ADMIN_EMAIL &&
    email.trim().toLowerCase() === process.env.ADMIN_EMAIL.trim().toLowerCase();
  let h = 0; for (const ch of email) h = (h * 31 + ch.charCodeAt(0)) | 0;
  const rand = Math.abs(h).toString().padStart(6, "0").slice(0, 6) + Math.floor(Math.random() * 90 + 10);
  const nick = nickname || email.split("@")[0];
  return {
    uid: "BT" + rand,
    email: email.trim().toLowerCase(),
    nickname: nick, name: nick,
    phone: phone || "", avatar: avatar || "", hash,
    plan: admin ? "premium" : "free",
    tier: admin ? "pro" : "free",
    emailVerified: admin ? true : false, phoneVerified: false,
    invitedBy: (invitedBy || "").trim().toUpperCase(), referrals: 0, referralRewarded: 0,
    isAdmin: admin, isLifetime: admin,
    createdAt: new Date().toISOString(),
  };
}
export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  secret: process.env.NEXTAUTH_SECRET,
  pages: { signIn: "/login" },
  providers: [
    CredentialsProvider({
      name: "Email",
      credentials: { email: { label: "Email", type: "email" }, password: { label: "密碼", type: "password" } },
      async authorize(cred) {
        if (!cred?.email || !cred.password) return null;
        const u = await getUser(cred.email);
        if (!u || !u.hash) return null;
        const ok = await bcrypt.compare(cred.password, u.hash);
        if (!ok) return null;
        return { id: u.uid, email: u.email, name: u.name };
      },
    }),
    ...(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET
      ? [GoogleProvider({ clientId: process.env.GOOGLE_CLIENT_ID, clientSecret: process.env.GOOGLE_CLIENT_SECRET })]
      : []),
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (token.email) {
        let u = await getUser(token.email);
        if (!u && account?.provider === "google") {
          u = newUser(token.email, (token.name as string) || "");
          u.emailVerified = true;
          await saveUser(u);
        }
        if (u) {
          token.uid = u.uid; token.plan = u.plan; token.tier = tierOf(u);
          token.isAdmin = u.isAdmin; token.isLifetime = u.isLifetime; token.planExpiry = u.planExpiry;
        }
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.uid = (token.uid as string) || "";
        session.user.plan = (token.plan as "free" | "premium") || "free";
        session.user.tier = (token.tier as Tier) || "free";
        session.user.isAdmin = !!token.isAdmin;
        session.user.isLifetime = !!token.isLifetime;
        session.user.planExpiry = token.planExpiry as string | undefined;
      }
      return session;
    },
  },
};
