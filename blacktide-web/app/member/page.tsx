"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { Crown, LogOut, Camera, Send, Save } from "lucide-react";
import { Card, SectionTitle, Badge } from "@/components/ui";
import { useApp } from "@/lib/store";
import { TIER_LABEL } from "@/lib/access";
interface Me { uid: string; email: string; name: string; phone: string; avatar: string; tier: "free" | "air" | "pro"; cycle: string | null; subAmount: number; planExpiry: string | null; isAdmin: boolean; createdAt: string; }
const inp = "w-full rounded-lg border border-white/10 bg-ink-900 px-3 py-2.5 text-sm outline-none focus:border-tide-500/40";
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (<div><div className="mb-1 text-xs text-slate-500">{label}</div>{children}</div>);
}
export default function MemberPage() {
  const { status } = useSession();
  const router = useRouter();
  const setPricingOpen = useApp((s) => s.setPricingOpen);
  const [me, setMe] = useState<Me | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [avatar, setAvatar] = useState("");
  const [saved, setSaved] = useState("");
  const [fb, setFb] = useState("");
  const [fbMsg, setFbMsg] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (status === "unauthenticated") router.replace("/login"); }, [status, router]);
  useEffect(() => {
    if (status !== "authenticated") return;
    fetch("/api/me").then((r) => r.json()).then((d) => {
      if (d && !d.error) { setMe(d); setName(d.name || ""); setPhone(d.phone || ""); setAvatar(d.avatar || ""); }
    }).catch(() => {});
  }, [status]);
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
    setBusy(true); setSaved("");
    try {
      const r = await fetch("/api/me", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, phone, avatar }) });
      setSaved(r.ok ? "已儲存" : "儲存失敗");
    } catch { setSaved("儲存失敗"); } finally { setBusy(false); }
  };
  const sendFeedback = async () => {
    if (!fb.trim()) { setFbMsg("請先填寫反饋內容"); return; }
    setBusy(true); setFbMsg("");
    try {
      const r = await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: fb }) });
      if (r.ok) { setFbMsg("已送出，感謝你的回饋！"); setFb(""); } else setFbMsg(((await r.json()).error) || "送出失敗");
    } catch { setFbMsg("送出失敗"); } finally { setBusy(false); }
  };
  if (status === "loading" || !me) return <div className="mx-auto mt-10 max-w-2xl"><Card className="h-40 animate-pulse" /></div>;
  const letter = (name || me.email || "?").slice(0, 1).toUpperCase();
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <SectionTitle title="會員中心" desc="個人資料、訂閱等級與意見反饋" />
      <Card className="p-5">
        <div className="flex items-center gap-4">
          <label className="relative h-16 w-16 shrink-0 cursor-pointer overflow-hidden rounded-full ring-1 ring-tide-400/40">
            {avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={avatar} alt="頭像" className="h-full w-full object-cover" />
            ) : (
              <span className="flex h-full w-full items-center justify-center bg-gradient-to-br from-tide-400 to-amber-700 text-lg font-bold text-ink-950">{letter}</span>
            )}
            <span className="absolute bottom-0 right-0 rounded-full bg-ink-900 p-1 text-tide-300"><Camera size={11} /></span>
            <input type="file" accept="image/*" className="hidden" onChange={(e) => onAvatar(e.target.files?.[0])} />
          </label>
          <div className="min-w-0">
            <div className="text-base font-bold">{name || "—"}</div>
            <div className="mt-0.5 font-mono text-[11px] text-slate-500">UID {me.uid}</div>
            <div className="mt-1"><Badge tone={me.tier === "pro" ? "amber" : me.tier === "air" ? "tide" : "slate"}>{TIER_LABEL[me.tier]}</Badge></div>
          </div>
          <div className="ml-auto flex flex-col gap-2">
            {me.tier !== "pro" && <button onClick={() => setPricingOpen(true)} className="flex items-center gap-1 rounded-lg bg-amber-500/15 px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/25"><Crown size={13} /> 升級</button>}
            {me.isAdmin && <a href="/admin" className="rounded-lg border border-tide-500/30 px-3 py-1.5 text-center text-xs text-tide-300 hover:bg-tide-500/10">後台</a>}
          </div>
        </div>
      </Card>
      <Card className="p-5">
        <div className="text-sm font-semibold">個人資料</div>
        <div className="mt-3 space-y-3">
          <Field label="姓名"><input className={inp} value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="電話"><input className={inp} value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
          <Field label="信箱"><input className={inp + " opacity-60"} value={me.email} disabled /></Field>
          <Field label="UID"><input className={inp + " font-mono opacity-60"} value={me.uid} disabled /></Field>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button disabled={busy} onClick={saveProfile} className="flex items-center gap-1.5 rounded-lg bg-tide-500/20 px-4 py-2 text-sm font-semibold text-tide-300 hover:bg-tide-500/30 disabled:opacity-50"><Save size={14} /> 儲存</button>
          {saved && <span className="text-xs text-slate-400">{saved}</span>}
        </div>
      </Card>
      <Card className="p-5">
        <div className="text-sm font-semibold">意見反饋</div>
        <p className="mt-1 text-xs text-slate-500">送出時會一併附上你的姓名、電話、信箱與 UID，方便我們聯繫。</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
          <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-600">姓名</div><div className="mt-0.5 truncate">{name || "—"}</div></div>
          <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-600">電話</div><div className="mt-0.5 truncate">{phone || "—"}</div></div>
          <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-600">信箱</div><div className="mt-0.5 truncate">{me.email}</div></div>
          <div className="rounded-lg bg-white/[0.03] p-2"><div className="text-slate-600">UID</div><div className="mt-0.5 truncate font-mono">{me.uid}</div></div>
        </div>
        <textarea value={fb} onChange={(e) => setFb(e.target.value)} rows={4} placeholder="想回報問題、許願功能或聊聊使用心得都歡迎…"
          className="mt-3 w-full rounded-lg border border-white/10 bg-ink-900 px-3 py-2.5 text-sm outline-none focus:border-tide-500/40" />
        <div className="mt-3 flex items-center gap-3">
          <button disabled={busy} onClick={sendFeedback} className="flex items-center gap-1.5 rounded-lg bg-tide-500/20 px-4 py-2 text-sm font-semibold text-tide-300 hover:bg-tide-500/30 disabled:opacity-50"><Send size={14} /> 送出反饋</button>
          {fbMsg && <span className="text-xs text-slate-400">{fbMsg}</span>}
        </div>
      </Card>
      <button onClick={() => signOut({ callbackUrl: "/" })} className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-white/10 py-2.5 text-sm text-slate-300 hover:bg-white/5"><LogOut size={14} /> 登出</button>
    </div>
  );
}
