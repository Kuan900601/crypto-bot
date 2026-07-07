"use client";
import { useEffect } from "react";
import { X } from "lucide-react";
import { C } from "@/lib/theme";
import { LEGAL_DOCS, LegalDocKey } from "@/lib/legalContent";
import LogoMark from "@/components/site/LogoMark";

/** 全站共用法律文件彈窗。內容唯一來源是 lib/legalContent.ts（與 /legal/* 靜態頁共用），
 *  不要在這裡另寫一份文字，否則兩處會不一致。 */
export default function LegalModal({ docKey, onClose }: { docKey: LegalDocKey | null; onClose: () => void }) {
  const doc = docKey ? LEGAL_DOCS[docKey] : null;
  useEffect(() => {
    if (!docKey) return;
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [docKey, onClose]);
  if (!doc) return null;
  return (
    <div onClick={onClose} className="legal-overlay" style={{
      position: "fixed", inset: 0, zIndex: 200, justifyContent: "center",
      padding: 20, paddingTop: "max(20px, env(safe-area-inset-top))", paddingBottom: 0,
      background: "rgba(2,4,9,0.7)", backdropFilter: "blur(5px)", animation: "fadeIn .25s",
    }}>
      <div onClick={(e) => e.stopPropagation()} className="legal-panel modal-sheet" style={{
        position: "relative", width: "100%", maxWidth: 640, display: "flex", flexDirection: "column",
        background: "linear-gradient(180deg, rgba(10,20,34,0.98), rgba(4,9,16,0.98))",
        border: `1px solid ${C.linePrimary}`, boxShadow: "0 30px 80px rgba(0,0,0,.6)", overflow: "hidden",
        paddingBottom: "max(8px, env(safe-area-inset-bottom))",
      }}>
        <div className="mx-auto mb-1 mt-2 h-1 w-10 shrink-0 rounded-full bg-white/10 sm:hidden" />
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, transparent, ${C.primary}, ${C.teal}, transparent)` }} />
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 24px", borderBottom: `1px solid ${C.line}`, flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <LogoMark size={36} />
            <div>
              <div style={{ fontWeight: 800, fontSize: 18, color: C.ink }}>{doc.title}</div>
              <div style={{ fontSize: 10.5, color: C.dim, marginTop: 2 }}>最後更新：{doc.updated}</div>
            </div>
          </div>
          <button onClick={onClose} className="ham" style={{ width: 36, height: 36, borderRadius: 10, border: `1px solid ${C.line}`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "transparent" }}>
            <X size={18} color={C.mut} />
          </button>
        </div>
        <div style={{ overflowY: "auto", padding: "20px 24px 28px" }}>
          {doc.sections.map(([h, p]) => (
            <div key={h} style={{ marginBottom: 20 }}>
              <h3 style={{ fontFamily: "inherit", fontSize: 14.5, fontWeight: 800, color: C.primary, margin: "0 0 8px" }}>{h}</h3>
              <p style={{ fontSize: 13.5, lineHeight: 1.85, color: "#B9C7D2", margin: 0 }}>{p}</p>
            </div>
          ))}
          <div style={{ marginTop: 8, paddingTop: 16, borderTop: `1px solid ${C.line}`, fontSize: 11.5, color: C.dim, lineHeight: 1.7 }}>
            本文件為平台服務說明之一部分。加密貨幣與槓桿商品風險極高，請自負盈虧。
          </div>
        </div>
      </div>
    </div>
  );
}
