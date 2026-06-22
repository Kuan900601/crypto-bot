import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#06070b", 900: "#0a0c12", 800: "#10131c", 700: "#161a26", 600: "#1e2433" },
        tide: { 300: "#f1dd9c", 400: "#e0bf5e", 500: "#d4af37", 600: "#a8842a" },
        // 對齊 blacktide-design-system.md 的 green/rose（做多/做空、獲利/虧損）
        up: "#46D6A0", down: "#F0697C"
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        display: ["Cinzel", "Songti TC", "PMingLiU", "Noto Serif TC", "serif"]
      }
    }
  },
  plugins: []
};
export default config;
