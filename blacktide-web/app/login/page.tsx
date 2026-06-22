"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signIn, getProviders } from "next-auth/react";
import { Camera, CheckCircle } from "lucide-react";
import { C, SERIF } from "@/lib/theme";
import LogoMark from "@/components/site/LogoMark";
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
        <LogoMark size={56} />
        <div className="mt-3" style={{ fontFamily: SERIF, fontSize: 17, fontWeight: 700, letterSpacing: 1, color: C.ink }}>黑潮 BLACKTIDE</div>
        <div style={{ fontFamily: SERIF, fontSize: 9.5, letterSpacing: 2.5, color: C.gold2 }}>SIGNALS · PRO TERMINAL</div>
      </div>
      <div className="mt-6 rounded-2xl p-5" style={{ border: `1px solid ${C.lineGold}`, background: "linear-gradient(180deg, rgba(16,30,48,0.78), rgba(6,16,30,0.7))" }}>
        {notice && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-up/20 bg-up/10 px-3 py-2 text-xs text-up">
            <CheckCircle size={13} /> {notice}
          </div>
        )}
        <div className="mb-4 grid grid-cols-2 gap-1 rounded-lg p-1" style={{ background: "rgba(255,255,255,0.04)", fontSize: 12.5, fontWeight: 700 }}>
          {(["login", "register"] as const).map((m) => (
            <button key={m} onClick={() => { setMode(m); setErr(""); }} className="rounded-md py-1.5" style={{
              background: mode === m ? "rgba(232,198,110,0.14)" : "transparent",
              color: mode === m ? C.gold : C.mut,
            }}>
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
        <button disabled={busy || !canSubmit} onClick={submit} className={busy || !canSubmit ? "" : "cta"} style={{
          marginTop: 16, width: "100%", borderRadius: 10, padding: "11px 0", fontSize: 14, fontWeight: 800,
          color: busy || !canSubmit ? C.mut : C.abyss,
          background: busy || !canSubmit ? "rgba(255,255,255,0.06)" : `linear-gradient(135deg,#FFF4D2,${C.gold} 45%,${C.gold2})`,
        }}>
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
