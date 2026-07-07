// ULTIMATE REDESIGN V1 色彩系統（Luxury Dark Fintech）。
// 全站共用色彩 / 字型常數：元件一律從這裡取值，不要另開分支硬寫色碼，避免日後改色要找全站。
// 2026-07 品牌決定：金色退場，主色改青色 #00D4FF（作者拍板）。
export const C = {
  // 背景層次（頁面 → 表面 → 卡片 → 浮起）
  abyss: "#05070A", deep: "#0B1117", navy: "#111827", current: "#1E293B",
  // 文字層次
  ink: "#F8FAFC", mut: "#94A3B8", dim: "#64748B",
  // 主色（青）：primary 主體、primary2 深一階（漸層收尾）、primaryDk 最深（邊框/陰影）
  primary: "#00D4FF", primary2: "#00A3CC", primaryDk: "#075985",
  // 次要點綴（同青色系，保留 key 供舊元件引用）
  teal: "#00D4FF", tealDk: "#0891B2",
  // 語意色
  green: "#10B981", rose: "#EF4444", amber: "#F59E0B",
  // 線條
  line: "rgba(255,255,255,0.08)", linePrimary: "rgba(0,212,255,0.18)",
} as const;

export const SERIF = '"Cinzel","Noto Serif TC",Georgia,serif';
export const SANS = '-apple-system,"PingFang TC","Microsoft JhengHei","Noto Sans TC",system-ui,sans-serif';
export const MONO = 'ui-monospace,"SF Mono",Menlo,monospace';
