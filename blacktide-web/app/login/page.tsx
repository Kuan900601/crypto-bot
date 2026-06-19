"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signIn, getProviders } from "next-auth/react";
import { Waves, Camera, CheckCircle } from "lucide-react";
const input = "w-full rounded-lg border border-white/10 bg-ink-900 px-3 py-2.5 text-sm outline-none focus:border-tide-500/40";
export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [nickname, setNickname] = useState("");
  const [phone, setPhone] = useState("");
  const [inviter, setInviter] = useState("");
  const [avatar, setAvatar] = useState("");
  const [remember, setRemember] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [hasGoogle, setHasGoogle] = useState(false);
  const [logoOk, setLogoOk] = useState(true);
  const [notice, setNotice] = useState("");
  const router = useRouter();
  useEffect(() => {
    getProviders().then((p) => setHasGoogle(!!p?.google)).catch(() => {});
    try {
      const sp = new URLSearchParams(window.location.search);
      if (sp.get("register") === "1") setMode("register");
      const inv = sp.get("inviter") || sp.get("ref");
      if (inv) { setInviter(inv.toUpperCase()); setMode("register"); }
      if (sp.get("verified") === "1") setNotice("✓ Email 驗證成功，請登入");
      if (sp.get("verifyError") === "1") setErr("驗證連結無效或已過期，請重新發送驗證信");
      // Restore remembered email
      const saved = localStorage.getItem("bt:remember_email");
      if (saved) { setEmail(saved); setRemember(true); }
    } catch {}
  }, []);
  const nextUrl = () => { try { return new URLSearchParams(window.location.search).get("next") || ""; } catch { return ""; } };
  const onAvatar = (file?: File) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const size = 96; const c = document.createElement("canvas"); c.width = size; c.height = size;
        const ctx = c.getContext("2d"); if (!ctx) return;
        const s = Math.min(img.width, img.height);
        ctx.drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, 0, 0, size, size);
        setAvatar(c.toDataURL("image/jpeg", 0.8));
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  };
  const submit = async () => {
    setErr(""); setBusy(true);
    try {
      if (mode === "register") {
        const r = await fetch("/api/register", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password: pw, nickname, phone, avatar, inviterUid: inviter }),
        });
        const d = await r.json();
        if (!r.ok) { setErr(d.error || "註冊失敗"); return; }
      }
      if (remember) { try { localStorage.setItem("bt:remember_email", email); } catch {} }
      else { try { localStorage.removeItem("bt:remember_email"); } catch {} }
      const res = await signIn("credentials", { email, password: pw, redirect: false });
      if (res?.error) { setErr("Email 或密碼錯誤"); return; }
      const nx = nextUrl();
      router.push(nx || (mode === "register" ? "/member" : "/"));
      router.refresh();
    } finally { setBusy(false); }
  };
  const canSubmit = mode === "login"
    ? !!email && !!pw
    : !!email && !!pw && !!nickname.trim() && !!phone.trim();
  return (
    <div className="mx-auto mt-[6vh] w-full max-w-sm">
      <div className="flex flex-col items-center">
        {logoOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src="/brand/logo.png" alt="黑潮 Signals" className="h-16 w-16 rounded-full object-cover ring-1 ring-tide-400/40" onError={() => setLogoOk(false)} />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-tide-400 to-tide-600 text-ink-950"><Waves size={26} strokeWidth={2.5} /></div>
        )}
        <div className="mt-3 text-lg font-bold tracking-wide">黑潮 BLACKTIDE</div>
        <div className="text-[11px] tracking-widest text-slate-500">SIGNALS · PRO TERMINAL</div>
      </div>
      <div className="mt-6 rounded-2xl border border-white/10 bg-ink-800/80 p-5">
        {notice && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-up/20 bg-up/10 px-3 py-2 text-xs text-up">
            <CheckCircle size={13} /> {notice}
          </div>
        )}
        <div className="mb-4 grid grid-cols-2 gap-1 rounded-lg bg-white/[0.04] p-1 text-xs font-semibold">
          {(["login", "register"] as const).map((m) => (
            <button key={m} onClick={() => { setMode(m); setErr(""); }}
              className={`rounded-md py-1.5 transition-colors ${mode === m ? "bg-tide-500/15 text-tide-300" : "text-slate-400"}`}>
              {m === "login" ? "登入" : "註冊"}
            </button>
          ))}
        </div>
        <div className="space-y-3">
          {mode === "register" && (
            <div className="flex items-center gap-2 rounded-xl border border-amber-500/25 bg-amber-500/8 px-3 py-2.5 text-xs text-amber-200">
              <span className="text-base shrink-0">🎁</span>
              <span><b>新用戶限定</b>：完成註冊自動獲得 <b>3 日 Plus 體驗</b>，即刻解鎖完整功能，無需付款。</span>
            </div>
          )}
          {mode === "register" && (
            <>
              <div className="flex items-center gap-3">
                <label className="relative h-14 w-14 shrink-0 cursor-pointer overflow-hidden rounded-full ring-1 ring-white/10">
                  {avatar ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={avatar} alt="頭像" className="h-full w-full object-cover" />
                  ) : (
                    <span className="flex h-full w-full items-center justify-center bg-white/5 text-slate-500"><Camera size={18} /></span>
                  )}
                  <input type="file" accept="image/*" className="hidden" onChange={(e) => onAvatar(e.target.files?.[0])} />
                </label>
                <div className="text-[11px] leading-relaxed text-slate-500">點左側圓圈上傳頭像（選填，會自動壓縮）</div>
              </div>
              <input className={input} placeholder="暱稱（必填）" value={nickname} onChange={(e) => setNickname(e.target.value)} />
              <input className={input} placeholder="手機號碼（必填）" value={phone} onChange={(e) => setPhone(e.target.value)} />
              <input className={input} placeholder="邀請人 UID（選填，例：BT12345678）" value={inviter} onChange={(e) => setInviter(e.target.value.toUpperCase())} />
            </>
          )}
          <input className={input} type="email" placeholder="Email（必填）" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <input className={input} type="password" placeholder={mode === "register" ? "密碼（至少 8 碼）" : "密碼"}
            value={pw} onChange={(e) => setPw(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
            autoComplete={mode === "login" ? "current-password" : "new-password"} />
          {mode === "login" && (
            <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)}
                className="h-3.5 w-3.5 rounded accent-tide-500" />
              記住帳號（Email）
            </label>
          )}
        </div>
        {err && <div className="mt-3 rounded-lg border border-down/20 bg-down/10 px-3 py-2 text-xs text-down">{err}</div>}
        <button disabled={busy || !canSubmit} onClick={submit}
          className="mt-4 w-full rounded-lg bg-tide-500/20 py-2.5 text-sm font-bold text-tide-300 hover:bg-tide-500/30 disabled:opacity-50">
          {busy ? "處理中…" : mode === "login" ? "登入" : "建立帳號"}
        </button>
        {hasGoogle && (
          <button onClick={() => signIn("google", { callbackUrl: nextUrl() || "/" })}
            className="mt-2 w-full rounded-lg border border-white/10 py-2.5 text-sm text-slate-200 hover:bg-white/5">
            使用 Google 登入
          </button>
        )}
        <div className="mt-4 text-[10px] leading-relaxed text-slate-600">
          {mode === "register" ? "註冊後會寄送驗證信，建議盡快驗證以保護帳號安全（非必要）。" : ""}
          註冊即表示同意服務條款、隱私權政策與風險揭露聲明。
        </div>
      </div>
    </div>
  );
}
