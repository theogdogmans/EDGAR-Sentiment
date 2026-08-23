import Link from "next/link";
import { loadSiteData } from "@/lib/data";
import { isDefaultEligible, isFdrSignificant } from "@/lib/phase5";

export const revalidate = 3600;

export default async function MethodologyPage() {
  const { companies, source } = await loadSiteData();
  const filings = companies.reduce((n, c) => n + (c.n_filings || 0), 0);
  const board = companies.filter(isDefaultEligible).length;
  const fdr = companies.filter(isFdrSignificant).length;

  return (
    <>
      <section className="hero">
        <div className="kicker">How it works</div>
        <h1>Methodology</h1>
        <p className="lede">
          Same-filing contemporaneous association between FinBERT-scored MD&amp;A tone and
          accounting YoY changes. Not prediction, not causation, not a trading signal.
        </p>
      </section>

      <div className="panel">
        <h2>Corpus (Phase 3 / 4)</h2>
        <ul className="prose-list">
          <li>
            Current S&amp;P 500 constituent universe (502 ticker rows; 499 unique SEC registrants
            after share-class consolidation)
          </li>
          <li>
            <strong>{filings.toLocaleString()}</strong> scored filings in the{" "}
            {source === "phase5_preview" ? "preview" : "published"} rollup
          </li>
          <li>
            Public default board: <strong>{board}</strong> companies with 10-Q NI n≥8
          </li>
          <li>
            FDR q&lt;.05 (ranking-eligible): <strong>{fdr}</strong> companies
          </li>
        </ul>
        <p>
          Overall finding: most companies show <strong>weak-to-modest</strong> contemporaneous
          relationships, while a <strong>minority</strong> show stronger and more consistent
          associations. Do not read this as universal tone/earnings alignment.
        </p>
      </div>

      <div className="panel">
        <h2>What we score</h2>
        <p>
          For each 10-K or 10-Q we extract <strong>Management&apos;s Discussion and Analysis</strong>{" "}
          only (10-K Item 7; 10-Q Item 2). Sentences are scored with{" "}
          <strong>FinBERT</strong> (<code>ProsusAI/finbert</code>). Long MD&amp;As are subsampled
          (evenly spaced, up to ~220 sentences). The filing score is the mean of sentence scores
          (positive − negative).
        </p>
        <p>
          Numbers come from SEC companyfacts XBRL for the <em>same</em> accession with period-integrity
          rules (duration bands, report-date tolerance). Agreement means tone and the metric moved
          in the same direction after excluding near-neutral cases.
        </p>
      </div>

      <div className="panel">
        <h2>Primary vs secondary analysis</h2>
        <ul className="prose-list">
          <li>
            <strong>Primary (company rankings):</strong> 10-Q MD&amp;A tone vs Net Income YoY
          </li>
          <li>
            <strong>Secondary:</strong> 10-K NI (shown collapsed on company pages; not mixed into
            the default board)
          </li>
          <li>
            <strong>Secondary:</strong> Revenue YoY where comparable
          </li>
          <li>
            <strong>Financials &amp; Real Estate:</strong> revenue comparison not used due to
            cross-company concept comparability
          </li>
        </ul>
        <p>
          Combined / pooled 10-K+10-Q correlations are exploratory only and are{" "}
          <strong>not</strong> the public ranking metric.
        </p>
      </div>

      <div className="panel">
        <h2>Statistics &amp; ranking rules</h2>
        <ul className="prose-list">
          <li>
            <strong>Spearman ρ</strong> is emphasized before Pearson for robustness to extreme YoY
            base effects
          </li>
          <li>
            <strong>Pearson r</strong> includes a Fisher 95% CI when n is sufficient
          </li>
          <li>
            <strong>FDR (Benjamini–Hochberg) q</strong> for multi-company claims — a badge means
            q&lt;.05 among ranking-eligible names, not proof or certainty
          </li>
          <li>
            Default public board: <strong>n≥8</strong>
          </li>
          <li>
            Limited sample: n=6–7 (company page only)
          </li>
          <li>
            Insufficient: n&lt;6
          </li>
        </ul>
      </div>

      <div className="panel">
        <h2>Limitations</h2>
        <ul className="prose-list">
          <li>Near-zero prior NI and loss↔profit flips can inflate Pearson</li>
          <li>MD&amp;A extraction quality varies by filing layout</li>
          <li>FinBERT sentence averages are not a human reading of emphasis or risk language</li>
          <li>Sector filing-weighted vs company-balanced results can differ materially</li>
          <li>10-K history remains short for many registrants</li>
        </ul>
      </div>

      <div className="panel">
        <h2>Data grain on the free-tier site</h2>
        <p>
          The live site reads slim aggregates from Supabase. Full MD&amp;A text and FinBERT runs
          stay on a local worker. Cloud storage holds sector dual-weight stats, company Phase 4
          fields, compact scatter points, and a few capped example filings.
        </p>
        <p className="hint">
          Prefer the company 10-Q NI board (Spearman, n≥8) and dual-weight sector panels — not a
          single pooled Pearson headline.
        </p>
      </div>

      <p className="note">
        <Link href="/">← Back to rankings</Link>
      </p>
    </>
  );
}
