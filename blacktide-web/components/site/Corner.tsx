import { C } from "@/lib/theme";

/** 卡片四角 HUD 角框。pos 對應四個角。 */
export default function Corner({ pos, color = C.gold2 }: { pos: "tl" | "tr" | "bl" | "br"; color?: string }) {
  const base = { position: "absolute" as const, width: 15, height: 15, borderColor: color, opacity: 0.55 };
  const m: Record<string, React.CSSProperties> = {
    tl: { top: 7, left: 7, borderTop: "1.5px solid", borderLeft: "1.5px solid" },
    tr: { top: 7, right: 7, borderTop: "1.5px solid", borderRight: "1.5px solid" },
    bl: { bottom: 7, left: 7, borderBottom: "1.5px solid", borderLeft: "1.5px solid" },
    br: { bottom: 7, right: 7, borderBottom: "1.5px solid", borderRight: "1.5px solid" },
  };
  return <div style={{ ...base, ...m[pos] }} />;
}
