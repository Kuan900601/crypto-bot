import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#06070b", 900: "#0a0c12", 800: "#10131c", 700: "#161a26", 600: "#1e2433" },
        // 品牌金（黑金主視覺）。沿用 tide 名稱，讓既有元件不改 class 就自動換成金色
        tide: { 300: "#f1dd9c", 400: "#e0bf5e", 500: "#d4af37", 600: "#a8842a" },
        up: "#10b981",
        down: "#f43f5e",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        display: ["Cinzel", "Songti TC", "PMingLiU", "Noto Serif TC", "serif"],
      },
    },
  },
  plugins: [],
};
export default config;
