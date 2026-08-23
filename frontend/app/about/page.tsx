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
          SEC filings are public, structured, and full of managerial language. This project asks a
          simple accounting question with modern tools: when management explains performance in the
          MD&amp;A, does the tone of that language tend to move with the numbers for the same
          period?
        </p>
        <p>
          It combines financial statement understanding, NLP scoring, careful period matching, and
          transparent statistics — presented so a second-year accounting student can follow the
          story without a stats course.
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
          <li>Sources: SEC EDGAR filings, XBRL companyfacts, FinBERT for MD&amp;A tone</li>
        </ul>
        <p>
          Purpose: explore <strong>contemporaneous</strong> relationships — not predict markets or
          recommend trades.
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
