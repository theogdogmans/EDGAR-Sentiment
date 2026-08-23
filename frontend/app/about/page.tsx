import Link from "next/link";
import { loadSiteData } from "@/lib/data";
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

      <div className="panel">
        <h2>What this is</h2>
        <ul className="prose-list">
          <li>Independent student research / portfolio project — not investment advice</li>
          <li>Current S&amp;P 500 constituents</li>
          <li>
            <strong>{filings.toLocaleString()}</strong> scored filings in the published rollup
          </li>
          <li>
            <strong>{board}</strong> companies on the main quarterly board · <strong>{fdr}</strong>{" "}
            remain notable after multiple-testing adjustment
          </li>
          <li>
            Sources: SEC filings, structured financial data (XBRL), and a finance-trained language
            model for MD&amp;A tone
          </li>
        </ul>
        <p>
          The purpose is to explore <strong>contemporaneous</strong> relationships between
          managerial language and financial results — not to predict markets or recommend trades.
        </p>
      </div>

      <div className="panel">
        <h2>Code &amp; transparency</h2>
        <p>
          Source repository:{" "}
          <a
            href="https://github.com/theogdogmans/EDGAR-Sentiment"
            target="_blank"
            rel="noopener noreferrer"
          >
            github.com/theogdogmans/EDGAR-Sentiment
          </a>
        </p>
        <p>
          <Link href="/methodology">Read the methodology →</Link>
        </p>
      </div>

      <p className="note">
        <Link href="/">← Overview</Link>
      </p>
    </>
  );
}
