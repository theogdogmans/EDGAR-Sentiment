import Link from "next/link";
import { loadSiteData } from "@/lib/data";
import { fmtCount } from "@/lib/format";
import { isDefaultEligible, isFdrSignificant } from "@/lib/phase5";

export const revalidate = 3600;

export default async function AboutPage() {
  const { companies } = await loadSiteData();
  const filings = companies.reduce((n, c) => n + (c.n_filings || 0), 0);
  const board = companies.filter(isDefaultEligible).length;
  const fdr = companies.filter(isFdrSignificant).length;

  return (
    <>
      <section className="hero">
        <div className="kicker">Project context</div>
        <h1>About this project</h1>
        <p className="lede">
          An independent accounting and data-analytics project exploring whether the tone of
          management&apos;s MD&amp;A tends to move with the same period&apos;s financial results.
        </p>
      </section>

      <section className="section open-section">
        <h2>Why it was built</h2>
        <p>
          This project began with a simple question about whether management&apos;s language changes
          with company performance. SEC filings are public and structured. They also contain a large
          amount of managerial explanation in the MD&amp;A.
        </p>
        <p>
          The work combines financial statement reading, language scoring, careful period matching,
          and transparent statistics. The goal is that a second-year accounting student can follow
          the main result without already knowing NLP or advanced statistical testing.
        </p>
      </section>

      <section className="section open-section">
        <h2>Scope</h2>
        <ul className="prose-list">
          <li>Current S&amp;P 500 constituents</li>
          <li>
            <strong>{fmtCount(filings)}</strong> scored filings in the published rollup
          </li>
          <li>
            <strong>{fmtCount(board)}</strong> companies on the main quarterly board ·{" "}
            <strong>{fmtCount(fdr)}</strong> remain notable after multiple-testing adjustment
          </li>
          <li>
            Sources: SEC EDGAR filings, XBRL companyfacts, and FinBERT for MD&amp;A tone scoring
          </li>
        </ul>
        <p>
          Purpose: explore <strong>contemporaneous</strong> relationships. This is not a forecast
          and not trading advice.
        </p>
      </section>

      <section className="section built-with" aria-label="Built with">
        <h2>Built with</h2>
        <ul className="built-list">
          <li>SEC EDGAR</li>
          <li>XBRL</li>
          <li>FinBERT</li>
          <li>Python</li>
          <li>Supabase</li>
          <li>Next.js</li>
        </ul>
      </section>

      <section className="section open-section">
        <h2>Links</h2>
        <p>
          <a
            href="https://github.com/theogdogmans/EDGAR-Sentiment"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub repository
          </a>
          {" · "}
          <Link href="/methodology">Methodology</Link>
          {" · "}
          <Link href="/">Live overview</Link>
        </p>
      </section>
    </>
  );
}
