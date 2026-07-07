"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { C } from "@/lib/theme";
export default function UserMenu() {
  const { data: session, status } = useSession();
  const [avatar, setAvatar] = useState("");
  const [name, setName] = useState("");
  const [isFounder, setIsFounder] = useState(false);
  useEffect(() => {
    if (status !== "authenticated") return;
    fetch("/api/me").then((r) => r.json()).then((d) => { if (d && !d.error) { setAvatar(d.avatar || ""); setName(d.name || ""); setIsFounder(!!d.isFounder); } }).catch(() => {});
  }, [status]);
  if (status === "loading") return <div className="h-8 w-8 animate-pulse rounded-full bg-white/10" />;
  if (!session?.user) return <Link href="/login" className="login-link shrink-0 whitespace-nowrap px-1.5 text-xs font-medium text-slate-400">登入</Link>;
  const letter = (name || session.user.name || session.user.email || "?").slice(0, 1).toUpperCase();
  return (
    <Link href="/member" aria-label="會員中心" className="relative block h-8 w-8 shrink-0 overflow-hidden rounded-full"
      style={isFounder ? { boxShadow: `0 0 0 1.5px ${C.primary}, 0 0 8px ${C.primary}99` } : { boxShadow: "0 0 0 1px rgba(94,234,212,0.4)" }}>
      {avatar ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={avatar} alt="頭像" className="h-full w-full object-cover" />
      ) : (
        <span className="flex h-full w-full items-center justify-center bg-gradient-to-br from-tide-400 to-amber-700 text-xs font-bold text-ink-950">{letter}</span>
      )}
      {isFounder && (
        <span aria-label="創始會員" className="absolute -bottom-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full text-[8px]" style={{ background: C.primary }}>
          🔥
        </span>
      )}
    </Link>
  );
}
