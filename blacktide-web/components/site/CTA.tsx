"use client";
import { ButtonHTMLAttributes } from "react";
import { C, SANS } from "@/lib/theme";

/** 主 CTA 按鈕：實色青底、深色字、沉穩柔影（REDESIGN V1，脈衝/掃光已退場）。
 *  注意：本元件只負責視覺，導頁/送出邏輯由呼叫端用 onClick 或包一層 <Link> 處理。 */
export default function CTA({ big, children, style, ...rest }: { big?: boolean } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={big ? "cta-big" : "cta"}
      style={{
        padding: big ? "16px 38px" : "13px 26px",
        borderRadius: 12,
        fontSize: big ? 16 : 15,
        fontWeight: 700,
        letterSpacing: "0.01em",
        cursor: "pointer",
        color: C.abyss,
        border: "none",
        fontFamily: SANS,
        background: C.primary,
        ...style,
      }}
      {...rest}
    >
      {children}
    </button>
  );
}
