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
    "Does management MD&A tone move with the same period's earnings? S&P 500 contemporaneous analysis — not a forecast.",
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
            <nav className="nav" aria-label="Main">
              <Link href="/">Overview</Link>
              <Link href="/#companies">Companies</Link>
              <Link href="/industries">Industries</Link>
              <Link href="/methodology">Methodology</Link>
              <Link href="/about">About</Link>
            </nav>
          </header>
          {children}
          <footer className="site-footer">
            <p>
              Contemporaneous research presentation — not predictive.{" "}
              <Link href="/methodology">How this works</Link>
              {" · "}
              <Link href="/about">About</Link>
            </p>
          </footer>
        </div>
      </body>
    </html>
  );
}
