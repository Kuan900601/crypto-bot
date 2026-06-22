// v8 視覺重做的共用色彩 / 字型常數，對應 blacktide-design-system.md §1-2。
// 新版共用元件（LogoMark/Corner/CTA/SiteBackground/Sidebar/Topbar/Footer/LegalModal…）一律從這裡取值，
// 不要另開分支硬寫色碼，避免日後改色要找全站。
export const C = {
  abyss: "#03060E", deep: "#06101E", navy: "#0A1A2E", current: "#13355A",
  ink: "#EEF4F2", mut: "#8FA6B5", dim: "#566B7C",
  gold: "#E8C66E", gold2: "#C9A24B", goldDk: "#8A6E22",
  teal: "#37D6C4", tealDk: "#1B8A82",
  green: "#46D6A0", rose: "#F0697C",
  line: "rgba(120,180,200,0.12)", lineGold: "rgba(232,198,110,0.16)",
} as const;

export const SERIF = '"Cinzel","Noto Serif TC",Georgia,serif';
export const SANS = '-apple-system,"PingFang TC","Microsoft JhengHei","Noto Sans TC",system-ui,sans-serif';
export const MONO = 'ui-monospace,"SF Mono",Menlo,monospace';
