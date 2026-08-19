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
  description: "Compare MD&A sentiment in SEC filings with the numbers in the statements.",
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
            <div className="kicker">S&amp;P 500 · live cache</div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
