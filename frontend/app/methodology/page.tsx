import Link from "next/link";
import { createSupabaseClient } from "@/lib/supabase";
import { fmtScore, toneClass } from "@/lib/format";
import type { ExampleFiling } from "@/lib/types";

export const revalidate = 3600;

export default async function MethodologyPage() {
  const supabase = createSupabaseClient();
  const { data } = await supabase
    .from("example_filings")
    .select("*")
    .not("risk_sentiment_score", "is", null)
    .limit(6);
  const demos = (data ?? []) as ExampleFiling[];

  return (
    <>
      <section className="hero">
        <div className="kicker">How it works</div>
        <h1>Methodology</h1>
        <p className="lede">
          What we score, what we leave alone, and why MD&amp;A is a biased but useful place to
          look for tone that should line up with the statements.
        </p>
      </section>

      <div className="panel">
        <h2>What we score</h2>
        <p>
          For each recent 10-K or 10-Q we extract{" "}
          <strong>Management&apos;s Discussion and Analysis</strong> only:
        </p>
        <ul className="prose-list">
          <li>
            <strong>10-K Item 7</strong> — MD&amp;A (through Item 8)
          </li>
          <li>
            <strong>10-Q Item 2</strong> — MD&amp;A (through Item 3)
          </li>
        </ul>
        <p>
          Sentences are scored with <strong>FinBERT</strong> (<code>ProsusAI/finbert</code>), a
          finance-tuned model. Long MD&amp;As are subsampled (evenly spaced, up to ~220 sentences)
          so an 80-page Item 7 is not fully scored. The filing score is the mean of sentence
          scores (positive − negative).
        </p>
        <p>
          Numbers come from SEC companyfacts XBRL for the <em>same</em> accession: year-over-year
          change in revenue and net income. Agreement means tone and the metric moved in the same
          direction. This is <strong>same-filing comparison</strong>, not a forecast or trading
          signal.
        </p>
      </div>

      <div className="panel">
        <h2>Which parts of a filing are more biased?</h2>
        <table>
          <thead>
            <tr>
              <th>Section</th>
              <th>Bias tendency</th>
              <th>In this project?</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>MD&amp;A (Item 7 / 2)</td>
              <td>
                Most management-controlled narrative. Forward-looking language often sounds more
                optimistic than the historical results discussion.
              </td>
              <td>Yes — primary corpus</td>
            </tr>
            <tr>
              <td>Item 1A Risk Factors</td>
              <td>
                Legally conservative, systematically negative, heavy boilerplate. Scoring at scale
                looks “bearish” even in good years.
              </td>
              <td>Bias demo only (few filings)</td>
            </tr>
            <tr>
              <td>Item 1 Business</td>
              <td>Descriptive, low discretion</td>
              <td>No</td>
            </tr>
            <tr>
              <td>Financial statements / notes / auditor</td>
              <td>Constrained or templated; the “numbers” side</td>
              <td>Numbers via XBRL only</td>
            </tr>
            <tr>
              <td>Earnings releases / shareholder letters</td>
              <td>Often more promotional than MD&amp;A</td>
              <td>No</td>
            </tr>
          </tbody>
        </table>
        <p className="hint" style={{ marginTop: 16 }}>
          Generic positive/negative word lists fail in finance (e.g. “liability”, “risk”). That is
          why we use FinBERT rather than a general lexicon.
        </p>
      </div>

      <div className="panel">
        <h2>MD&amp;A vs Risk Factors (live demos)</h2>
        <p className="hint">
          A handful of 10-Ks also get Item 1A scored so you can see the section bias without storing
          a second full S&amp;P 500 corpus.
        </p>
        {!demos.length ? (
          <p className="muted">
            No bias demos synced yet. After scoring filings locally, run{" "}
            <code>push_all()</code> with the service role key.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Filing</th>
                <th>MD&amp;A</th>
                <th>Item 1A</th>
                <th>Gap</th>
              </tr>
            </thead>
            <tbody>
              {demos.map((f) => {
                const gap =
                  f.sentiment_score != null && f.risk_sentiment_score != null
                    ? f.sentiment_score - f.risk_sentiment_score
                    : null;
                return (
                  <tr key={f.accession}>
                    <td>
                      <Link href={`/company/${f.ticker}/filing/${f.accession}`}>
                        {f.ticker} · {f.form} · {f.filed}
                      </Link>
                    </td>
                    <td className={toneClass(f.sentiment_score)}>{fmtScore(f.sentiment_score)}</td>
                    <td className={toneClass(f.risk_sentiment_score)}>
                      {fmtScore(f.risk_sentiment_score)}
                    </td>
                    <td className={toneClass(gap)}>{fmtScore(gap)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h2>Free-tier data grain</h2>
        <p>
          The live site reads <strong>industry and company aggregates</strong> from Supabase Free
          (500 MB database). Full MD&amp;A text and FinBERT runs stay on a local worker. Cloud
          storage holds:
        </p>
        <ul className="prose-list">
          <li>
            <code>sector_stats</code> — pooled correlations by GICS sector
          </li>
          <li>
            <code>company_stats</code> — one slim row per ticker (compact scatter points, no
            sentence blobs)
          </li>
          <li>
            <code>example_filings</code> — a few case studies with sentence highlights
          </li>
        </ul>
        <p>
          Company Pearson r with n≈8 is weak. Prefer industry pooled r as the headline, and treat
          company rankings as illustrations with the sample-size caveat.
        </p>
      </div>
    </>
  );
}
