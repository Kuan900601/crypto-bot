"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
export default function UserMenu() {
  const { data: session, status } = useSession();
  const [avatar, setAvatar] = useState("");
  const [name, setName] = useState("");
  useEffect(() => {
    if (status !== "authenticated") return;
    fetch("/api/me").then((r) => r.json()).then((d) => { if (d && !d.error) { setAvatar(d.avatar || ""); setName(d.name || ""); } }).catch(() => {});
  }, [status]);
  if (status === "loading") return <div className="h-8 w-8 animate-pulse rounded-full bg-white/10" />;
  if (!session?.user) return <Link href="/login" className="rounded-lg bg-tide-500/15 px-3 py-1.5 text-xs font-semibold text-tide-300 hover:bg-tide-500/25">登入</Link>;
  const letter = (name || session.user.name || session.user.email || "?").slice(0, 1).toUpperCase();
  return (
    <Link href="/member" aria-label="會員中心" className="block h-8 w-8 overflow-hidden rounded-full ring-1 ring-tide-400/40">
      {avatar ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={avatar} alt="頭像" className="h-full w-full object-cover" />
      ) : (
        <span className="flex h-full w-full items-center justify-center bg-gradient-to-br from-tide-400 to-amber-700 text-xs font-bold text-ink-950">{letter}</span>
      )}
    </Link>
  );
}
