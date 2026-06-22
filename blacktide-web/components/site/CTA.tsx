"use client";
import { ButtonHTMLAttributes } from "react";
import { C, SANS } from "@/lib/theme";

/** 主 CTA 按鈕：金漸層底 + 掃光 + 呼吸脈衝。big 給轉換頁/結尾用更強脈衝。
 *  注意：本元件只負責視覺，導頁/送出邏輯由呼叫端用 onClick 或包一層 <Link> 處理。 */
export default function CTA({ big, children, style, ...rest }: { big?: boolean } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={big ? "cta-big" : "cta"}
      style={{
        padding: big ? "17px 42px" : "15px 30px",
        borderRadius: 13,
        fontSize: big ? 17 : 16,
        fontWeight: 800,
        cursor: "pointer",
        color: C.abyss,
        border: "none",
        fontFamily: SANS,
        background: `linear-gradient(135deg,#FFF4D2,${C.gold} 45%,${C.gold2})`,
        ...style,
      }}
      {...rest}
    >
      {children}
    </button>
  );
}
