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

const siteUrl = "https://www.edgarsentiment.site";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "EDGAR Sentiment — Does the Tone Match the Numbers?",
    template: "%s · EDGAR Sentiment",
  },
  description:
    "An analysis of 9,697 S&P 500 SEC filings comparing management's MD&A tone with quarterly financial performance. Exploratory research — not investment advice.",
  openGraph: {
    title: "EDGAR Sentiment — Does the Tone Match the Numbers?",
    description:
      "An analysis of 9,697 S&P 500 SEC filings comparing management's MD&A tone with quarterly financial performance.",
    url: "/",
    siteName: "EDGAR Sentiment",
    images: [
      {
        url: "/og-linkedin-v2.png",
        width: 1200,
        height: 627,
        alt: "Does the tone match the numbers?",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "EDGAR Sentiment — Does the Tone Match the Numbers?",
    description:
      "9,697 S&P 500 SEC filings: MD&A tone vs quarterly financial performance.",
    images: ["/og-linkedin-v2.png"],
  },
  icons: {
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
  },
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
              <Link href="/#explore">Companies</Link>
              <Link href="/industries">Industries</Link>
              <Link href="/methodology">Methodology</Link>
              <Link href="/about">About</Link>
            </nav>
          </header>
          {children}
          <footer className="site-footer">
            <div className="footer-links">
              <Link href="/">Overview</Link>
              <Link href="/#explore">Companies</Link>
              <Link href="/industries">Industries</Link>
              <Link href="/methodology">Methodology</Link>
              <Link href="/about">About</Link>
              <a
                href="https://github.com/theogdogmans/EDGAR-Sentiment"
                target="_blank"
                rel="noopener noreferrer"
              >
                GitHub
              </a>
            </div>
            <p className="footer-note">
              Exploratory accounting/data analysis. Not investment advice. Contemporaneous
              association only — not prediction or causation.
            </p>
          </footer>
        </div>
      </body>
    </html>
  );
}
