import "./globals.css";
import Providers from "@/components/Providers";
import FxBackground from "@/components/FxBackground";
import Shell from "@/components/Shell";
export const metadata = {
  title: "黑潮 BLACKTIDE | 專業交易分析平台",
  description: "Bybit 即時行情、AI 分析、黑潮船長訊號、即時新聞與異常監控",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "黑潮 BLACKTIDE", statusBarStyle: "black-translucent" as const },
  icons: { icon: "/brand/logo.png", apple: "/brand/logo.png" },
};
export const viewport = { themeColor: "#06070b", width: "device-width", initialScale: 1, viewportFit: "cover" as const };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body>
        <div className="brand-hero" aria-hidden />
        <Providers>
          <FxBackground />
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
