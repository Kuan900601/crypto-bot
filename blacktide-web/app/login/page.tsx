"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signIn, getProviders } from "next-auth/react";
import { Waves } from "lucide-react";
const input = "w-full rounded-lg border border-white/10 bg-ink-900 px-3 py-2.5 text-sm outline-none focus:border-tide-500/40";
export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [hasGoogle, setHasGoogle] = useState(false);
  const [logoOk, setLogoOk] = useState(true);
  const router = useRouter();
  useEffect(() => { getProviders().then((p) => setHasGoogle(!!p?.google)).catch(() => {}); }, []);
  const submit = async () => {
    setErr(""); setBusy(true);
    try {
      if (mode === "register") {
        const r = await fetch("/api/register", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password: pw, name }),
        });
        if (!r.ok) { setErr((await r.json()).error || "註冊失敗"); return; }
      }
      const res = await signIn("credentials", { email, password: pw, redirect: false });
      if (res?.error) { setErr("Email 或密碼錯誤"); return; }
      router.push("/signals");
      router.refresh();
    } finally { setBusy(false); }
  };
  return (
    <div className="mx-auto mt-[6vh] w-full max-w-sm">
      <div className="flex flex-col items-center">
        {logoOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src="/brand/logo.png" alt="黑潮 Signals" className="h-16 w-16 rounded-full object-cover ring-1 ring-tide-400/40" onError={() => setLogoOk(false)} />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-tide-400 to-tide-600 text-ink-950"><Waves size={26} strokeWidth={2.5} /></div>
        )}
        <div className="mt-3 font-display text-lg font-bold tracking-wide text-gold">黑潮 BLACKTIDE</div>
        <div className="text-[11px] tracking-widest text-slate-500">SIGNALS · PRO TERMINAL</div>
      </div>
      <div className="mt-6 rounded-2xl border border-white/10 bg-ink-800/80 p-5">
        <div className="mb-4 grid grid-cols-2 gap-1 rounded-lg bg-white/[0.04] p-1 text-xs font-semibold">
          {(["login", "register"] as const).map((m) => (
            <button key={m} onClick={() => { setMode(m); setErr(""); }}
              className={`rounded-md py-1.5 transition-colors ${mode === m ? "bg-tide-500/15 text-tide-300" : "text-slate-400"}`}>
              {m === "login" ? "登入" : "註冊"}
            </button>
          ))}
        </div>
        <div className="space-y-3">
          {mode === "register" && <input className={input} placeholder="名稱" value={name} onChange={(e) => setName(e.target.value)} />}
          <input className={input} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input className={input} type="password" placeholder={mode === "register" ? "密碼（至少 8 碼）" : "密碼"}
            value={pw} onChange={(e) => setPw(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") submit(); }} />
        </div>
        {err && <div className="mt-3 rounded-lg border border-down/20 bg-down/10 px-3 py-2 text-xs text-down">{err}</div>}
        <button disabled={busy || !email || !pw} onClick={submit}
          className="mt-4 w-full rounded-lg bg-tide-500/20 py-2.5 text-sm font-bold text-tide-300 hover:bg-tide-500/30 disabled:opacity-50">
          {busy ? "處理中…" : mode === "login" ? "登入" : "建立帳號"}
        </button>
        {hasGoogle && (
          <button onClick={() => signIn("google", { callbackUrl: "/signals" })}
            className="mt-2 w-full rounded-lg border border-white/10 py-2.5 text-sm text-slate-200 hover:bg-white/5">
            使用 Google 登入
          </button>
        )}
        <div className="mt-4 text-[10px] leading-relaxed text-slate-600">
          用戶資料存於 Upstash Redis（未設定時為記憶體模式，重啟即清空）。本服務為策略驗證期數據，不構成投資建議。
        </div>
      </div>
    </div>
  );
}
