import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nexus Financial — Bitcoin Banking Platform",
  description:
    "Production-grade Bitcoin banking with double-entry ledger, GEM-ATR cards, and enterprise compliance.",
  keywords: ["bitcoin", "banking", "fintech", "ledger", "cards"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans bg-gray-950 text-gray-100 antialiased">
        {children}
      </body>
    </html>
  );
}
