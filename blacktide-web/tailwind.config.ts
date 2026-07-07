import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ULTIMATE REDESIGN V1 深色層次（頁面 → 表面 → 卡片 → 浮起）
        ink: { 950: "#05070A", 900: "#0B1117", 800: "#111827", 700: "#16202E", 600: "#1E293B" },
        // tide = 品牌青色階（2026-07 起金色退場，主色 #00D4FF）
        tide: { 300: "#7EE8FF", 400: "#33DDFF", 500: "#00D4FF", 600: "#00A3CC" },
        up: "#10B981", down: "#EF4444",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        display: ["Cinzel", "Songti TC", "PMingLiU", "Noto Serif TC", "serif"]
      },
      // Magic UI 元件（marquee/orbit/shiny-text/rainbow）需要的動畫：
      // vendored 元件寫的是 Tailwind v4 @theme 語法，本專案是 v3，必須在這裡補定義才會動
      keyframes: {
        marquee: {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(calc(-100% - var(--gap)))" },
        },
        "marquee-vertical": {
          from: { transform: "translateY(0)" },
          to: { transform: "translateY(calc(-100% - var(--gap)))" },
        },
        orbit: {
          "0%": { transform: "rotate(calc(var(--angle) * 1deg)) translateY(calc(var(--radius) * 1px)) rotate(calc(var(--angle) * -1deg))" },
          "100%": { transform: "rotate(calc(var(--angle) * 1deg + 360deg)) translateY(calc(var(--radius) * 1px)) rotate(calc((var(--angle) * -1deg) - 360deg))" },
        },
        "shiny-text": {
          "0%, 90%, 100%": { "background-position": "calc(-100% - var(--shiny-width)) 0" },
          "30%, 60%": { "background-position": "calc(100% + var(--shiny-width)) 0" },
        },
        rainbow: {
          "0%": { "background-position": "0%" },
          "100%": { "background-position": "200%" },
        },
        "border-beam": {
          "100%": { "offset-distance": "100%" },
        },
        "grid-pattern": {
          "0%": { opacity: "0.5" },
          "50%": { opacity: "1" },
          "100%": { opacity: "0.5" },
        },
      },
      animation: {
        marquee: "marquee var(--duration) infinite linear",
        "marquee-vertical": "marquee-vertical var(--duration) linear infinite",
        orbit: "orbit calc(var(--duration)*1s) linear infinite",
        "shiny-text": "shiny-text 8s infinite",
        rainbow: "rainbow var(--speed, 2s) infinite linear",
        "border-beam": "border-beam calc(var(--duration)*1s) infinite linear",
      },
    }
  },
  plugins: []
};
export default config;
