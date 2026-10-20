import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Reliability Lab",
  description: "Evaluation and regression testing for AI applications",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="top">
          <Link href="/">AI Reliability Lab</Link>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
