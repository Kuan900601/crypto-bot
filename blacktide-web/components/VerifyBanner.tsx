"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Mail, X, Check } from "lucide-react";

const DISMISS_KEY = "bt:verify_banner_dismissed";

export default function VerifyBanner() {
  const { data: session } = useSession();
  const [dismissed, setDismissed] = useState(true);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    try { setDismissed(localStorage.getItem(DISMISS_KEY) === "1"); } catch { setDismissed(false); }
  }, []);

  if (dismissed || !session || session.user?.emailVerified) return null;

  const dismiss = () => { setDismissed(true); try { localStorage.setItem(DISMISS_KEY, "1"); } catch {} };
  const resend = async () => {
    setBusy(true);
    try { await fetch("/api/resend-verification", { method: "POST" }); setSent(true); } catch {} finally { setBusy(false); }
  };

  return (
    <div className="mb-4 flex items-center gap-2 rounded-xl border border-tide-500/25 bg-tide-500/10 px-4 py-2.5 text-xs text-tide-200">
      <Mail size={14} className="shrink-0" />
      <span>📧 建議驗證信箱以保護帳號安全（非必要）</span>
      {sent ? (
        <span className="ml-auto flex items-center gap-1 text-up"><Check size={13} /> 驗證信已重新寄出</span>
      ) : (
        <button onClick={resend} disabled={busy} className="ml-auto rounded-lg bg-tide-500/20 px-3 py-1 font-semibold hover:bg-tide-500/30 disabled:opacity-50">
          {busy ? "寄送中…" : "重新發送驗證信"}
        </button>
      )}
      <button onClick={dismiss} className="rounded-md p-1 text-tide-400/60 hover:text-tide-200"><X size={13} /></button>
    </div>
  );
}
