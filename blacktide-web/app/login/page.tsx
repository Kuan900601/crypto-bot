"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";

const GOOGLE_ON = process.env.NEXT_PUBLIC_GOOGLE_ENABLED === "true";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      if (mode === "register") {
        const r = await fetch("/api/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, name }),
        });
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          const map: Record<string, string> = {
            EMAIL_TAKEN: "此 Email 已註冊",
            WEAK_PASSWORD: "密碼至少 6 碼",
            BAD_EMAIL: "Email 格式不正確",
          };
          throw new Error(map[j.error] || j.error || "註冊失敗");
        }
      }
      const res = await signIn("credentials", { email, password, redirect: false });
      if (res?.error) throw new Error("帳號或密碼錯誤");
      router.push("/account");
      router.refresh();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm py-10">
      <h1 className="text-xl font-semibold text-slate-100">
        {mode === "login" ? "登入黑潮" : "註冊黑潮"}
      </h1>
      <p className="mt-1 text-xs text-slate-500">登入後可訂閱 Premium，解鎖完整信號。</p>

      <form onSubmit={submit} className="mt-6 space-y-3">
        {mode === "register" && (
          <input
            className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm outline-none focus:border-tide-500"
            placeholder="暱稱（可留空）"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        )}
        <input
          type="email"
          required
          className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm outline-none focus:border-tide-500"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password"
          required
          className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm outline-none focus:border-tide-500"
          placeholder="密碼（至少 6 碼）"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {err && <div className="text-xs text-down">{err}</div>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-tide-500 px-4 py-2 text-sm font-semibold text-ink-950 hover:bg-tide-400 disabled:opacity-50"
        >
          {busy ? "處理中…" : mode === "login" ? "登入" : "註冊並登入"}
        </button>
      </form>

      {GOOGLE_ON && (
        <button
          onClick={() => signIn("google", { callbackUrl: "/account" })}
          className="mt-3 w-full rounded-lg border border-ink-600 bg-ink-800 px-4 py-2 text-sm text-slate-200 hover:bg-ink-700"
        >
          用 Google 登入
        </button>
      )}

      <button
        onClick={() => { setErr(null); setMode(mode === "login" ? "register" : "login"); }}
        className="mt-4 w-full text-center text-xs text-tide-400 hover:text-tide-300"
      >
        {mode === "login" ? "還沒有帳號？前往註冊" : "已有帳號？前往登入"}
      </button>
    </div>
  );
}
