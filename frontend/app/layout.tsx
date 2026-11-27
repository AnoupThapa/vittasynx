import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Vittasynx — Receivables intelligence",
  description: "Know what you are owed, how late customers pay and what needs attention.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
