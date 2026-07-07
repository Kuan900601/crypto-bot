import "./globals.css";
import Providers from "@/components/Providers";
import SiteBackground from "@/components/site/SiteBackground";
import Shell from "@/components/Shell";
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

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
    <html lang="zh-Hant" className={cn("font-sans", geist.variable)}>
      <body>
        <div className="brand-hero" aria-hidden />
        <Providers>
          <SiteBackground />
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
