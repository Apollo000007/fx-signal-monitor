import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Oracle of Olympus · FX Signal",
  description: "ギリシャ神話 × 悟り — マルチタイムフレーム FX 神託ダッシュボード",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" className="dark">
      <body className="min-h-screen bg-bg bg-grid-fade antialiased">
        <div className="min-h-screen bg-grid relative">
          {/* 悟りの曼荼羅 — 背景装飾 */}
          <div
            aria-hidden
            className="pointer-events-none fixed inset-0 mandala-bg opacity-[0.08]"
          />
          <div
            aria-hidden
            className="pointer-events-none fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px] rounded-full bg-aura-gradient opacity-[0.12] blur-3xl"
          />
          <div className="relative">{children}</div>
        </div>
      </body>
    </html>
  );
}
