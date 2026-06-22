"use client";
import { useState } from "react";
import { C, SERIF } from "@/lib/theme";
import { LegalDocKey } from "@/lib/legalContent";
import LogoMark from "@/components/site/LogoMark";
import LegalModal from "@/components/LegalModal";

const LEGAL_LINKS: [string, LegalDocKey][] = [
  ["服務條款", "terms"],
  ["免責聲明", "disclaimer"],
  ["隱私權政策", "privacy"],
  ["風險揭露聲明", "risk"],
];

export default function Footer() {
  const [legal, setLegal] = useState<LegalDocKey | null>(null);
  const year = new Date().getFullYear();
  return (
    <footer style={{ marginTop: 40, paddingTop: 24, paddingBottom: 8, borderTop: `1px solid ${C.line}` }}>
      <LegalModal docKey={legal} onClose={() => setLegal(null)} />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <LogoMark size={26} />
          <span style={{ fontFamily: SERIF, fontWeight: 700, fontSize: 14, color: C.gold }}>黑潮 BLACKTIDE</span>
        </div>
        <nav className="flex flex-wrap gap-x-4 gap-y-1 sm:ml-auto">
          {LEGAL_LINKS.map(([label, key]) => (
            <button key={key} onClick={() => setLegal(key)} className="login-link" style={{ fontSize: 12, color: C.mut, background: "none", border: "none", cursor: "pointer", padding: 0 }}>
              {label}
            </button>
          ))}
        </nav>
      </div>
      <p style={{ marginTop: 12, fontSize: 11, lineHeight: 1.7, color: C.dim }}>
        © {year} 黑潮 BLACKTIDE。本平台提供之行情、分析與訊號僅供研究與教育參考，不構成投資建議或要約。加密貨幣與槓桿商品風險極高，請自負盈虧。
      </p>
    </footer>
  );
}
