import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import bcrypt from "bcryptjs";
import { redisGet, redisSet } from "./redis";

export interface WebUser {
  uid: string; email: string; name: string; hash?: string;
  plan: "free" | "premium"; planExpiry?: string;
  isAdmin: boolean; isLifetime: boolean; createdAt: string;
}

const mem = new Map<string, WebUser>();
const KEY = (email: string) => "web:user:" + email.trim().toLowerCase();

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
}

export function isPremium(u: { plan?: string; isLifetime?: boolean; planExpiry?: string } | null | undefined): boolean {
  if (!u) return false;
  if (u.isLifetime) return true;
  return u.plan === "premium" && (!u.planExpiry || new Date(u.planExpiry) > new Date());
}

export function newUser(email: string, name: string, hash?: string): WebUser {
  const admin = !!process.env.ADMIN_EMAIL &&
    email.trim().toLowerCase() === process.env.ADMIN_EMAIL.trim().toLowerCase();
  let h = 0; for (const ch of email) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return {
    uid: "BT-" + Math.abs(h).toString(36).toUpperCase(),
    email: email.trim().toLowerCase(),
    name: name || email.split("@")[0],
    hash,
    plan: admin ? "premium" : "free",
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
          token.uid = u.uid; token.plan = u.plan;
          token.isAdmin = u.isAdmin; token.isLifetime = u.isLifetime;
          token.planExpiry = u.planExpiry;
        }
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.uid = (token.uid as string) || "";
        session.user.plan = (token.plan as "free" | "premium") || "free";
        session.user.isAdmin = !!token.isAdmin;
        session.user.isLifetime = !!token.isLifetime;
        session.user.planExpiry = token.planExpiry as string | undefined;
      }
      return session;
    },
  },
};
