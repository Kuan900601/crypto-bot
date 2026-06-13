import type { NextAuthOptions } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import { verifyUser, getUser, ensureOAuthUser, isPremiumActive } from "./users";

// NextAuth 設定。Credentials（email + bcrypt）為主；設了 GOOGLE_* 才額外開 Google 登入。
// Session 走 JWT，但每次都從 Redis 撈最新 plan，付款升級後不需重新登入即生效。

const providers: NextAuthOptions["providers"] = [
  Credentials({
    name: "Email",
    credentials: {
      email: { label: "Email", type: "email" },
      password: { label: "密碼", type: "password" },
    },
    async authorize(creds) {
      if (!creds?.email || !creds?.password) return null;
      const u = await verifyUser(creds.email, creds.password);
      if (!u) return null;
      return { id: u.email, email: u.email, name: u.name };
    },
  }),
];

if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    })
  );
}

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  secret: process.env.NEXTAUTH_SECRET,
  providers,
  pages: { signIn: "/login" },
  callbacks: {
    async signIn({ user, account }) {
      // Google 首登 → 建立 user 紀錄；credentials 已在 authorize 驗過
      if (account?.provider === "google" && user.email) {
        await ensureOAuthUser(user.email, user.name ?? undefined);
      }
      return true;
    },
    async session({ session }) {
      if (session.user?.email) {
        const u = await getUser(session.user.email);
        session.user.plan = isPremiumActive(u) ? "premium" : "free";
        session.user.isAdmin = !!u?.isAdmin;
        session.user.planExpiry = u?.planExpiry;
      }
      return session;
    },
  },
};
