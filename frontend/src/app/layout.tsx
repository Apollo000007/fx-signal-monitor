import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FX Signal Monitor",
  description: "Multi-timeframe FX signal dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" className="dark">
      <body className="min-h-screen bg-bg bg-grid-fade antialiased">
        <div className="min-h-screen bg-grid">
          {children}
        </div>
      </body>
    </html>
  );
}
