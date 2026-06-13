import type { Metadata, Viewport } from "next";
import "./globals.css";
import Nav from "@/components/Nav";
import MobileNav from "@/components/MobileNav";
import AuthProvider from "@/components/AuthProvider";

export const metadata: Metadata = {
  title: "黑潮 BLACKTIDE | 專業交易分析平台",
  description: "Bybit 即時行情、K 線分析、黑潮 Signals 訊號與市場情報",
};

export const viewport: Viewport = { themeColor: "#06070b" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body className="min-h-screen text-slate-200 antialiased">
        <div className="brand-hero" aria-hidden />
        <AuthProvider>
          <div className="flex">
            <Nav />
            <main className="min-h-screen flex-1 px-4 py-6 pb-24 md:pb-6 lg:px-8">{children}</main>
          </div>
          <MobileNav />
        </AuthProvider>
      </body>
    </html>
  );
}
