import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#070b12", 900: "#0a0f18", 800: "#0e1521", 700: "#131c2b", 600: "#1a2436" },
        tide: { 300: "#67e8f9", 400: "#22d3ee", 500: "#06b6d4", 600: "#0891b2" },
        up: "#10b981",
        down: "#f43f5e"
      },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] }
    }
  },
  plugins: []
};
export default config;
