import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ElfomoFi Depth Lab · Live virtual order book",
  description: "Explore live ElfomoFi liquidity on Base with quote-size sweeps, marginal depth, engine ladders, and reproducible block snapshots.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
