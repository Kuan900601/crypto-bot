"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Card, SectionTitle, Progress, Badge } from "@/components/ui";
import { Gift, Copy, Check, Users, Sparkles } from "lucide-react";
import { C } from "@/lib/theme";
interface Ref { uid: string; referrals: number; rewarded: number; monthsEarned: number; inThisCycle: number; toNext: number; }
export default function ActivityPage() {
  const { status } = useSession();
  const [r, setR] = useState<Ref | null>(null);
  const [origin, setOrigin] = useState("");
  const [copied, setCopied] = useState("");
  useEffect(() => {
    setOrigin(window.location.origin);
    // 未登入不打受保護 API（401 會在 console 留 error，鎖定層本來就會蓋住頁面）
    if (status !== "authenticated") return;
    fetch("/api/referral").then((x) => x.json()).then((d) => { if (d && !d.error) setR(d); }).catch(() => {});
  }, [status]);
  const link = r ? origin + "/login?register=1&inviter=" + r.uid : "";
  const copy = (text: string, key: string) => {
    try { navigator.clipboard.writeText(text); setCopied(key); setTimeout(() => setCopied(""), 1500); } catch {}
  };
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <SectionTitle title="福利中心" desc="參加活動賺取訂閱與好康，更多活動陸續推出" />
      {/* 3 日試用卡 */}
      <div className="flex items-start gap-3 rounded-2xl border border-amber-500/25 bg-gradient-to-r from-amber-500/8 to-transparent p-4">
        <span className="shrink-0 text-2xl">🎁</span>
        <div>
          <div className="font-bold text-amber-200">新用戶 3 日 Plus 免費體驗</div>
          <div className="mt-0.5 text-xs leading-relaxed text-slate-400">
            所有新用戶完成註冊後自動獲得 3 天 Plus 訂閱試用，完整體驗 AI 分析、即時新聞與美股功能。試用到期後自動回歸免費方案，無需任何付款資訊。
          </div>
        </div>
      </div>
      <Card className="relative overflow-hidden p-0">
        
        <div className="flex items-center gap-3 border-b border-white/5 bg-gradient-to-r from-amber-500/10 to-transparent px-5 py-4" style={{ borderBottom: `1px solid ${C.linePrimary}` }}>
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-500/15 text-amber-300"><Gift size={22} /></span>
          <div>
            <div className="text-sm font-bold text-amber-100">邀請好友註冊</div>
            <div className="text-[11px] text-slate-400">每成功邀請 5 人，免費獲得 1 個月 Plus 訂閱（可累加）</div>
          </div>
          <Badge tone="amber"><Sparkles size={12} /> 進行中</Badge>
        </div>
        <div className="space-y-4 p-5">
          <div>
            <div className="mb-1 text-xs text-slate-500">你的專屬邀請碼（UID）</div>
            <div className="flex items-center gap-2">
              <div className="flex-1 rounded-lg border border-white/10 bg-ink-900 px-3 py-2.5 font-mono text-sm">{r?.uid || "—"}</div>
              <button onClick={() => copy(r?.uid || "", "uid")} className="shrink-0 rounded-lg border border-white/10 px-3 py-2.5 hover:bg-white/5">
                {copied === "uid" ? <Check size={14} className="text-up" /> : <Copy size={14} className="text-slate-400" />}
              </button>
            </div>
          </div>
          <div>
            <div className="mb-1 text-xs text-slate-500">分享註冊連結（好友開啟後邀請碼自動帶入）</div>
            <div className="flex items-center gap-2">
              <div className="flex-1 truncate rounded-lg border border-white/10 bg-ink-900 px-3 py-2.5 text-xs text-slate-400">{link || "—"}</div>
              <button onClick={() => copy(link, "link")} className="shrink-0 rounded-lg border border-white/10 px-3 py-2.5 hover:bg-white/5">
                {copied === "link" ? <Check size={14} className="text-up" /> : <Copy size={14} className="text-slate-400" />}
              </button>
            </div>
          </div>
          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 font-semibold"><Users size={15} className="text-tide-300" /> 已成功邀請</span>
              <span className="font-mono text-lg font-bold text-tide-200">{r?.referrals ?? 0} 人</span>
            </div>
            <div className="mt-3"><Progress value={((r?.inThisCycle ?? 0) / 5) * 100} tone="amber" /></div>
            <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-500">
              <span>距離下一個月 Plus 還差 <b className="text-amber-300">{r?.toNext ?? 5}</b> 人</span>
              <span>本輪 {r?.inThisCycle ?? 0}/5</span>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-up/15 bg-up/5 px-4 py-3">
            <span className="text-xs text-slate-400">已獲得獎勵</span>
            <span className="ml-auto font-mono text-sm font-bold text-up">{r?.monthsEarned ?? 0} 個月 Plus</span>
          </div>
          <div className="text-[11px] leading-relaxed text-slate-500">
            活動規則：好友於註冊時填入你的 UID（或透過你的專屬連結註冊）即算一次成功邀請。每累積 5 位成功邀請自動發放 1 個月 Plus 訂閱（從現有到期日往後累加）。本活動辦法與獎勵內容以平台公告為準。
          </div>
        </div>
      </Card>
      <Card className="p-5 text-center text-sm text-slate-500">更多活動籌備中，敬請期待</Card>
    </div>
  );
}
