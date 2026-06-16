import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import bcrypt from "bcryptjs";
import { redisGet, redisSet, redisSAdd } from "./redis";
export type Tier = "free" | "air" | "pro";
export interface WebUser {
  uid: string; email: string; name: string; phone?: string; avatar?: string; hash?: string;
  plan: "free" | "premium"; planExpiry?: string;
  tier: Tier; cycle?: "monthly" | "yearly"; subAmount?: number; subStartedAt?: string;
  isAdmin: boolean; isLifetime: boolean; createdAt: string;
}
const mem = new Map<string, WebUser>();
const KEY = (email: string) => "web:user:" + email.trim().toLowerCase();
export const USERS_SET = "web:users";
export async function getUser(email: string): Promise<WebUser | null> {
  const k = KEY(email);
  const raw = await redisGet(k);
  if (raw) { try { return JSON.parse(raw) as WebUser; } catch {} }
  return mem.get(k) ?? null;
}
export async function saveUser(u: WebUser): Promise<void> {
  const k = KEY(u.email);
  const ok = await redisSet(k, JSON.stringify(u));
  if (!ok) mem.set(k, u);
  await redisSAdd(USERS_SET, u.email);
}
export function tierOf(u: { isAdmin?: boolean; isLifetime?: boolean; tier?: string; plan?: string; planExpiry?: string } | null | undefined): Tier {
  if (!u) return "free";
  if (u.isAdmin || u.isLifetime) return "pro";
  if (u.planExpiry && new Date(u.planExpiry).getTime() < Date.now()) return "free";
  if (u.tier === "air" || u.tier === "pro") return u.tier;
  if (u.plan === "premium") return "pro";
  return "free";
}
export function isPremium(u: { plan?: string; isLifetime?: boolean; tier?: string } | null | undefined): boolean {
  return tierOf(u) !== "free";
}
export function newUser(email: string, name: string, hash?: string, phone?: string, avatar?: string): WebUser {
  const admin = !!process.env.ADMIN_EMAIL &&
    email.trim().toLowerCase() === process.env.ADMIN_EMAIL.trim().toLowerCase();
  let h = 0; for (const ch of email) h = (h * 31 + ch.charCodeAt(0)) | 0;
  const rand = Math.abs(h).toString().padStart(6, "0").slice(0, 6) + Math.floor(Math.random() * 90 + 10);
  return {
    uid: "BT" + rand,
    email: email.trim().toLowerCase(),
    name: name || email.split("@")[0],
    phone: phone || "", avatar: avatar || "", hash,
    plan: admin ? "premium" : "free",
    tier: admin ? "pro" : "free",
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
