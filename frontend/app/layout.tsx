import type { Metadata } from "next";
import { Source_Sans_3, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const sans = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-sans",
});

const serif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-serif",
});

export const metadata: Metadata = {
  title: "edgar-sentiment",
  description:
    "Contemporaneous association between S&P 500 MD&A tone and same-filing YoY net income (10-Q primary). Not a forecast.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${serif.variable}`}>
        <div className="shell">
          <header className="masthead">
            <Link className="wordmark" href="/">
              edgar-<span>sentiment</span>
            </Link>
            <nav className="nav">
              <Link href="/">Rankings</Link>
              <Link href="/methodology">Methodology</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
