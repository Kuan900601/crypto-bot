import { DefaultSession } from "next-auth";
declare module "next-auth" {
  interface Session {
    user: DefaultSession["user"] & {
      uid: string;
      plan: "free" | "premium";
      isAdmin: boolean;
      isLifetime: boolean;
      planExpiry?: string;
    };
  }
}
declare module "next-auth/jwt" {
  interface JWT {
    uid?: string; plan?: string; isAdmin?: boolean; isLifetime?: boolean; planExpiry?: string;
  }
}
