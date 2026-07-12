"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import Link from "next/link";
import { Crown, LogOut, Camera, Send, Save, BadgeCheck, ShieldAlert, Gift, CheckCircle2, Bell } from "lucide-react";
import { Card, SectionTitle, Badge } from "@/components/ui";
import { useApp } from "@/lib/store";
import { TIER_LABEL } from "@/lib/access";
import { C } from "@/lib/theme";
interface Me { uid: string; email: string; nickname: string; phone: string; avatar: string; tier: "free" | "air" | "pro"; cycle: string | null; subAmount: number; planExpiry: string | null; emailVerified: boolean; phoneVerified: boolean; invitedBy: string; referrals: number; referralRewarded: number; notifyEnabled: boolean; quietStart: string; quietEnd: string; isAdmin: boolean; isFounder: boolean; createdAt: string; }
const inp = "w-full rounded-lg border border-white/10 bg-ink-900 px-3 py-2.5 text-sm outline-none focus:border-tide-500/40";
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (<div><div className="mb-1 text-xs text-slate-500">{label}</div>{children}</div>);
}
const fmtDate = (s: string | null) => { if (!s) return "—"; try { return new Date(s).toLocaleDateString("zh-TW"); } catch { return "—"; } };
export default function MemberPage() {
  const { status } = useSession();
  const router = useRouter();
  const setPricingOpen = useApp((s) => s.setPricingOpen);
  const pushToast = useApp((s) => s.pushToast);
  const [me, setMe] = useState<Me | null>(null);
  const [nickname, setNickname] = useState("");
  const [phone, setPhone] = useState("");
  const [avatar, setAvatar] = useState("");
  const [fb, setFb] = useState("");
  const [anon, setAnon] = useState(false);
  const [busy, setBusy] = useState(false);
  const [paid, setPaid] = useState(false);
  const [vSent, setVSent] = useState(false);
  const [vCode, setVCode] = useState("");
  const [vMsg, setVMsg] = useState("");
  const [vBusy, setVBusy] = useState(false);
  const [notifyOn, setNotifyOn] = useState(true);
  const [quietOn, setQuietOn] = useState(false);
  const [quietStart, setQuietStart] = useState("23:00");
  const [quietEnd, setQuietEnd] = useState("08:00");
  useEffect(() => { if (status === "unauthenticated") router.replace("/login"); }, [status, router]);
  useEffect(() => {
    try {
      const sp = new URLSearchParams(window.location.search);
      if (sp.get("paid") === "1") { setPaid(true); window.history.replaceState({}, "", "/member"); }
    } catch {}
  }, []);
  const loadMe = () => fetch("/api/me").then((r) => r.json()).then((d) => {
    if (d && !d.error) {
      setMe(d); setNickname(d.nickname || ""); setPhone(d.phone || ""); setAvatar(d.avatar || "");
      setNotifyOn(d.notifyEnabled !== false);
      if (d.quietStart && d.quietEnd) { setQuietOn(true); setQuietStart(d.quietStart); setQuietEnd(d.quietEnd); }
    }
  }).catch(() => {});
  useEffect(() => { if (status === "authenticated") loadMe(); }, [status]);
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
  const saveProfile = async () => {
    setBusy(true);
    try {
      const r = await fetch("/api/me", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nickname, phone, avatar }) });
      pushToast({ msg: r.ok ? "個人資料已儲存" : "儲存失敗，請稍後再試", type: r.ok ? "success" : "error" });
    } catch { pushToast({ msg: "儲存失敗，請稍後再試", type: "error" }); } finally { setBusy(false); }
  };
  const saveNotify = async () => {
    setBusy(true);
    try {
      const r = await fetch("/api/me", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notify: { enabled: notifyOn, quietStart: quietOn ? quietStart : "", quietEnd: quietOn ? quietEnd : "" } }) });
      pushToast({ msg: r.ok ? "通知設定已儲存" : "儲存失敗，請稍後再試", type: r.ok ? "success" : "error" });
    } catch { pushToast({ msg: "儲存失敗，請稍後再試", type: "error" }); } finally { setBusy(false); }
  };
  const sendFeedback = async () => {
    if (!fb.trim()) { pushToast({ msg: "請先填寫反饋內容", type: "info" }); return; }
    setBusy(true);
    try {
      const r = await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: fb, anonymous: anon }) });
      if (r.ok) { pushToast({ msg: "已送出，感謝你的回饋！", type: "success" }); setFb(""); }
      else pushToast({ msg: ((await r.json()).error) || "送出失敗", type: "error" });
    } catch { pushToast({ msg: "送出失敗，請稍後再試", type: "error" }); } finally { setBusy(false); }
  };
  const sendCode = async () => {
    setVBusy(true); setVMsg("");
    try {
      const r = await fetch("/api/verify/email", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "send" }) });
      const d = await r.json();
      if (!d.configured) setVMsg("寄信服務尚未設定（管理員需在 Vercel 設定 RESEND_API_KEY 並重新部署）");
      else { setVSent(true); setVMsg(d.sent ? "驗證碼已寄出，請查收信箱（含垃圾信匣），於下方輸入。" : "寄送失敗：" + (d.info || "未知原因") + "（仍可稍後重試）"); }
    } catch { setVMsg("寄送失敗"); } finally { setVBusy(false); }
  };
  const checkCode = async () => {
    setVBusy(true); setVMsg("");
    try {
      const r = await fetch("/api/verify/email", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "check", code: vCode }) });
      if (r.ok) { setVMsg("信箱已驗證 ✓"); setVSent(false); setVCode(""); loadMe(); }
      else setVMsg(((await r.json()).error) || "驗證失敗");
    } catch { setVMsg("驗證失敗"); } finally { setVBusy(false); }
  };
  if (status === "loading" || !me) return <div className="mx-auto mt-10 max-w-2xl"><Card className="h-40 animate-pulse" /></div>;
  const letter = (nickname || me.email || "?").slice(0, 1).toUpperCase();
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <SectionTitle title="會員中心" desc="個人資料、訂閱等級、帳號驗證、通知與意見反饋" />
      {paid && (
        <div className="flex items-center gap-2 rounded-xl border border-up/25 bg-up/10 px-4 py-2.5 text-xs text-up">
          <CheckCircle2 size={18} className="shrink-0" />
          <span>付款流程完成！款項於區塊鏈確認後，訂閱會自動開通，可能需稍候片刻再重新整理。</span>
        </div>
      )}
      <Card className="relative overflow-hidden p-5">
        
        <div className="flex items-center gap-4">
          <label className="relative h-16 w-16 shrink-0 cursor-pointer overflow-hidden rounded-full" style={{ boxShadow: me.isFounder ? `0 0 0 2px ${C.primary}, 0 0 14px ${C.primary}99` : `0 0 0 1px ${C.linePrimary}` }}>
            {avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={avatar} alt="頭像" className="h-full w-full object-cover" />
            ) : (
              <span className="flex h-full w-full items-center justify-center bg-gradient-to-br from-tide-400 to-tide-600 text-lg font-bold text-ink-950">{letter}</span>
            )}
            <span className="absolute bottom-0 right-0 rounded-full bg-ink-900 p-1 text-tide-300"><Camera size={11} /></span>
            <input type="file" accept="image/*" className="hidden" onChange={(e) => onAvatar(e.target.files?.[0])} />
            {me.isFounder && (
              <span aria-label="創始會員" className="absolute -top-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full text-[10px]" style={{ background: C.primary }}>🔥</span>
            )}
          </label>
          <div className="min-w-0">
            <div className="text-base font-bold">{nickname || "—"}</div>
            <div className="mt-0.5 font-mono text-[11px] text-slate-500">UID {me.uid}</div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Badge tone={me.tier === "pro" ? "amber" : me.tier === "air" ? "tide" : "slate"}>{TIER_LABEL[me.tier]}</Badge>
              {me.isFounder && <Badge tone="amber">🔥 創始會員</Badge>}
              {me.tier !== "free" && me.planExpiry && <span className="text-[11px] text-slate-500">到期 {fmtDate(me.planExpiry)}</span>}
            </div>
          </div>
          <div className="ml-auto flex flex-col gap-2">
            {me.tier !== "pro" && <button onClick={() => setPricingOpen(true)} className="flex items-center gap-1 rounded-lg bg-amber-500/15 px-3 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/25"><Crown size={13} /> 升級</button>}
            {me.isAdmin && <a href="/admin" className="rounded-lg border border-tide-500/30 px-3 py-2 text-center text-xs text-tide-300 hover:bg-tide-500/10">後台</a>}
          </div>
        </div>
      </Card>
      <Card className="p-5">
        <div className="text-sm font-semibold">帳號驗證</div>
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500">信箱</span>
            <span className="text-sm text-slate-300">{me.email}</span>
            {me.emailVerified ? <Badge tone="up"><BadgeCheck size={12} /> 已驗證</Badge> : <Badge tone="amber"><ShieldAlert size={12} /> 未驗證</Badge>}
            {!me.emailVerified && <button disabled={vBusy} onClick={sendCode} className="ml-auto rounded-lg bg-tide-500/15 px-3 py-2 text-xs font-semibold text-tide-300 hover:bg-tide-500/25 disabled:opacity-50">發送驗證碼</button>}
          </div>
          {!me.emailVerified && vSent && (
            <div className="flex items-center gap-2">
              <input className={inp + " font-mono tracking-widest"} placeholder="輸入 6 位數驗證碼" value={vCode} onChange={(e) => setVCode(e.target.value.replace(/\D/g, "").slice(0, 6))} />
              <button disabled={vBusy || vCode.length !== 6} onClick={checkCode} className="shrink-0 rounded-lg bg-tide-500/20 px-4 py-2.5 text-sm font-semibold text-tide-300 disabled:opacity-50">驗證</button>
            </div>
          )}
          {vMsg && <div className="text-xs text-slate-400">{vMsg}</div>}
          <div className="flex flex-wrap items-center gap-2 border-t border-white/5 pt-3">
            <span className="text-xs text-slate-500">手機</span>
            <span className="text-sm text-slate-300">{me.phone || "—"}</span>
            {me.phoneVerified ? <Badge tone="up"><BadgeCheck size={12} /> 已驗證</Badge> : <Badge tone="slate">未啟用</Badge>}
          </div>
        </div>
      </Card>
      <Card className="p-5">
        <label className="flex min-h-[44px] cursor-pointer items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold"><Bell size={15} className="text-tide-300" /> 推播通知</div>
          <span className="relative inline-flex items-center">
            <input type="checkbox" checked={notifyOn} onChange={(e) => setNotifyOn(e.target.checked)} className="peer sr-only" />
            <span className="h-6 w-11 rounded-full bg-white/10 transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:bg-tide-500 peer-checked:after:translate-x-5" />
          </span>
        </label>
        <p className="mt-1 text-xs text-slate-500">開啟後，新訊號與重要提醒會推播到你的裝置。</p>
        {notifyOn && (
          <div className="mt-3 space-y-3">
            <label className="flex min-h-[44px] items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={quietOn} onChange={(e) => setQuietOn(e.target.checked)} className="h-4 w-4 accent-tide-500" />
              夜間勿擾（此時段不推播）
            </label>
            {quietOn && (
              <div className="flex items-center gap-2 text-sm">
                <input type="time" value={quietStart} onChange={(e) => setQuietStart(e.target.value)} className={inp + " w-auto"} />
                <span className="text-slate-500">至</span>
                <input type="time" value={quietEnd} onChange={(e) => setQuietEnd(e.target.value)} className={inp + " w-auto"} />
              </div>
            )}
          </div>
        )}
        <div className="mt-4 flex items-center gap-3">
          <button disabled={busy} onClick={saveNotify} className="flex items-center gap-1.5 rounded-lg bg-tide-500/20 px-4 py-2 text-sm font-semibold text-tide-300 hover:bg-tide-500/30 disabled:opacity-50"><Save size={14} /> 儲存通知設定</button>
        </div>
        <div className="mt-2 text-[10px] leading-relaxed text-slate-600">註：實際推播到手機需後續接通推播服務，此處先保存你的偏好。</div>
      </Card>
      <Card className="p-5">
        <div className="text-sm font-semibold">個人資料</div>
        <div className="mt-3 space-y-3">
          <Field label="暱稱"><input className={inp} value={nickname} onChange={(e) => setNickname(e.target.value)} /></Field>
          <Field label="手機"><input className={inp} value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
          <Field label="信箱"><input className={inp + " opacity-60"} value={me.email} disabled /></Field>
          <Field label="UID"><input className={inp + " font-mono opacity-60"} value={me.uid} disabled /></Field>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button disabled={busy} onClick={saveProfile} className="flex items-center gap-1.5 rounded-lg bg-tide-500/20 px-4 py-2 text-sm font-semibold text-tide-300 hover:bg-tide-500/30 disabled:opacity-50"><Save size={14} /> 儲存</button>
        </div>
      </Card>
      <Link href="/activity" className="block">
        <Card className="flex items-center gap-3 p-4">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/15 text-amber-300"><Gift size={18} /></span>
          <div className="min-w-0">
            <div className="text-sm font-semibold">邀請好友拿訂閱</div>
            <div className="text-[11px] text-slate-500">已成功邀請 {me.referrals} 人 · 每 5 人送 1 個月 Plus</div>
          </div>
          <span className="ml-auto text-xs text-tide-300">前往活動 →</span>
        </Card>
      </Link>
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold">意見反饋</div>
          <label className="flex min-h-[44px] cursor-pointer items-center gap-1.5 text-xs text-slate-400">
            <input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} className="h-4 w-4 accent-tide-500" />
            匿名反饋
          </label>
        </div>
        <p className="mt-1 text-xs text-slate-500">{anon ? "匿名送出：不會附帶你的暱稱、信箱、手機與 UID。" : "送出時會一併附上你的暱稱、電話、信箱與 UID，方便我們聯繫。"}</p>
        {!anon && (
          <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
            <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-600">暱稱</div><div className="mt-0.5 truncate">{nickname || "—"}</div></div>
            <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-600">手機</div><div className="mt-0.5 truncate">{phone || "—"}</div></div>
            <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-600">信箱</div><div className="mt-0.5 truncate">{me.email}</div></div>
            <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-600">UID</div><div className="mt-0.5 truncate font-mono">{me.uid}</div></div>
          </div>
        )}
        <textarea value={fb} onChange={(e) => setFb(e.target.value)} rows={4} placeholder="想回報問題、許願功能或聊聊使用心得都歡迎…"
          className="mt-3 w-full rounded-lg border border-white/10 bg-ink-900 px-3 py-2.5 text-sm outline-none focus:border-tide-500/40" />
        <div className="mt-3 flex items-center gap-3">
          <button disabled={busy} onClick={sendFeedback} className="flex items-center gap-1.5 rounded-lg bg-tide-500/20 px-4 py-2 text-sm font-semibold text-tide-300 hover:bg-tide-500/30 disabled:opacity-50"><Send size={14} /> 送出反饋</button>
        </div>
      </Card>
      <button onClick={() => signOut({ callbackUrl: "/login" })} className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-white/10 py-2.5 text-sm text-slate-300 hover:bg-white/5"><LogOut size={14} /> 登出</button>
    </div>
  );
}
