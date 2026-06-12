import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "黑潮 BLACKTIDE · Signals Console",
  description: "黑潮 Signals 交易信號儀表板（唯讀，串接 bot_data）",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body className="min-h-screen bg-ink-950 text-slate-200 antialiased">
        <div className="flex">
          <Nav />
          <main className="min-h-screen flex-1 px-4 py-6 lg:px-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
