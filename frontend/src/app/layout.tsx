import type { Metadata } from "next";
import "./globals.css";
import { activeVisualTheme, isEvaTheme } from "@/lib/visualTheme";

export const metadata: Metadata = {
  title: isEvaTheme ? "為替通貨資産量産機 弐号機" : "Oracle of Olympus · FX Signal",
  description: isEvaTheme
    ? "白黒赤の作戦端末風マルチタイムフレーム FX シグナルダッシュボード"
    : "ギリシャ神話 × 悟り — マルチタイムフレーム FX 神託ダッシュボード",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" className="dark" data-theme={activeVisualTheme}>
      <body className="min-h-screen bg-bg bg-grid-fade antialiased">
        <div className="min-h-screen bg-grid relative overflow-hidden">
          {isEvaTheme ? (
            <>
              <div aria-hidden className="pointer-events-none fixed inset-0 eva-command-bg" />
              <div aria-hidden className="pointer-events-none fixed inset-x-0 top-0 h-2 bg-accent-red" />
              <div aria-hidden className="pointer-events-none fixed left-0 top-0 h-screen w-3 eva-stripe opacity-80" />
            </>
          ) : (
            <>
              <div
                aria-hidden
                className="pointer-events-none fixed inset-0 mandala-bg opacity-[0.08]"
              />
              <div
                aria-hidden
                className="pointer-events-none fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px] rounded-full bg-aura-gradient opacity-[0.12] blur-3xl"
              />
            </>
          )}
          <div className="relative">{children}</div>
        </div>
      </body>
    </html>
  );
}
