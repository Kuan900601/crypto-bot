import Link from "next/link";
const LINKS = [
  { href: "/legal/terms", label: "服務條款" },
  { href: "/legal/disclaimer", label: "免責聲明" },
  { href: "/legal/privacy", label: "隱私權政策" },
  { href: "/legal/risk", label: "風險揭露聲明" },
];
export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-10 border-t border-white/5 pb-2 pt-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/logo.png" alt="黑潮" className="h-6 w-6 rounded-full opacity-80" />
          <span className="font-display text-sm font-bold text-gold">黑潮 BLACKTIDE</span>
        </div>
        <nav className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400 sm:ml-auto">
          {LINKS.map((l) => <Link key={l.href} href={l.href} className="hover:text-tide-300">{l.label}</Link>)}
        </nav>
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-slate-600">
        © {year} 黑潮 BLACKTIDE。本平台提供之行情、分析與訊號僅供研究與教育參考，不構成投資建議或要約。加密貨幣與槓桿商品風險極高，請自負盈虧。
      </p>
    </footer>
  );
}
