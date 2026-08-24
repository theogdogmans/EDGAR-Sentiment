import Link from "next/link";
import type { ReactNode } from "react";
import MethodologyNav from "@/components/MethodologyNav";
import { loadSiteData } from "@/lib/data";
import { fmtCount } from "@/lib/format";
import { isDefaultEligible, isFdrSignificant } from "@/lib/phase5";

export const revalidate = 3600;

function Section({
  id,
  title,
  plain,
  technical,
}: {
  id: string;
  title: string;
  plain: ReactNode;
  technical?: ReactNode;
}) {
  return (
    <section id={id} className="meth-section open-section">
      <h2>{title}</h2>
      <div className="plain-box">
        <div className="plain-label">Plain English</div>
        <div className="plain-body">{plain}</div>
      </div>
      {technical ? (
        <details className="tech-details">
          <summary>Technical detail</summary>
          <div className="tech-box">
            <div className="plain-body">{technical}</div>
          </div>
        </details>
      ) : null}
    </section>
  );
}

export default async function MethodologyPage() {
  const { companies, source } = await loadSiteData();
  const filings = companies.reduce((n, c) => n + (c.n_filings || 0), 0);
  const board = companies.filter(isDefaultEligible).length;
  const fdr = companies.filter(isFdrSignificant).length;

  return (
    <div className="meth-layout">
      <MethodologyNav />
      <div className="meth-main">
      <section className="hero">
        <div className="kicker">How it works</div>
        <h1>Methodology</h1>
        <p className="lede">
          This page explains the project in plain language first, then adds technical detail for
          readers who want the exact rules. This is not a forecast, not causation, and not trading advice.
        </p>
      </section>

      <div className="panel soft">
        <h2>At a glance</h2>
        <ul className="prose-list">
          <li>
            <strong>{fmtCount(filings)}</strong> scored filings in the{" "}
            {source === "phase5_preview" ? "preview" : "published"} rollup
          </li>
          <li>
            Main company board: <strong>{fmtCount(board)}</strong> companies with at least 8 quarterly
            observations
          </li>
          <li>
            <strong>{fmtCount(fdr)}</strong> companies remain notable after the multiple-testing adjustment
          </li>
        </ul>
      </div>

      <Section
        id="research-question"
        title="Research question"
        plain={
          <p>
            When management writes about the business in a quarterly filing, does the tone of that
            writing tend to move in the same direction as the company&apos;s earnings change for
            that same period?
          </p>
        }
        technical={
          <p>
            Same-filing contemporaneous association between FinBERT-scored MD&amp;A tone and YoY
            net income (primary) / revenue (secondary). Not prediction or causation.
          </p>
        }
      />

      <Section
        id="data"
        title="Data"
        plain={
          <p>
            The project covers current S&amp;P 500 companies. Each company contributes recent
            annual (10-K) and quarterly (10-Q) SEC filings. The public rankings focus on quarterly
            filings with enough matched observations.
          </p>
        }
        technical={
          <p>
            502 ticker rows; 499 unique SEC registrants after share-class consolidation. Primary
            board requires n≥8 on 10-Q net income pairs. Limited sample (n=6–7) appears on company
            pages only.
          </p>
        }
      />

      <Section
        id="mda"
        title="MD&A"
        plain={
          <p>
            Management&apos;s Discussion and Analysis, or MD&amp;A, is the section where management
            explains performance, trends, and risks in its own words. This project scores that
            section only, not the whole filing.
          </p>
        }
        technical={
          <p>
            Extract Item 7 (10-K) or Item 2 (10-Q). Long MD&amp;As are subsampled (evenly spaced, up
            to ~220 sentences).
          </p>
        }
      />

      <Section
        id="finbert"
        title="Tone scoring (FinBERT)"
        plain={
          <p>
            FinBERT is a language model trained for financial text. It estimates whether a sentence
            sounds positive, neutral, or negative. It is a structured reading aid, not a human judgment
            of emphasis or intent.
          </p>
        }
        technical={
          <p>
            Model: <code>ProsusAI/finbert</code>. Sentence scores combine into a filing-level tone
            score.
          </p>
        }
      />

      <Section
        id="sentiment-score"
        title="Sentiment score"
        plain={
          <p>
            Each filing gets one tone score from roughly −1 (more negative language) to +1 (more
            positive language). Higher means the MD&amp;A language leaned more positive on average.
          </p>
        }
        technical={
          <p>
            Filing score = mean of sentence scores, where each sentence score is positive share
            minus negative share.
          </p>
        }
      />

      <Section
        id="financial-data"
        title="Financial data"
        plain={
          <p>
            For each filing we look up how net income (and, where comparable, revenue) changed
            versus the same quarter one year earlier. That year-over-year change is what we compare
            to tone.
          </p>
        }
        technical={
          <p>
            Primary metric: 10-Q net income YoY. Secondary: 10-Q revenue (where comparable) and
            10-K net income. Financials and Real Estate revenue comparisons are not used due to
            cross-company concept differences.
          </p>
        }
      />

      <Section
        id="xbrl"
        title="XBRL"
        plain={
          <p>
            XBRL is structured financial data reported to the SEC. This project uses those structured
            figures rather than scraping tables by hand.
          </p>
        }
        technical={<p>SEC companyfacts XBRL for the same accession as the filing text.</p>}
      />

      <Section
        id="period-matching"
        title="Period matching"
        plain={
          <p>
            Tone and numbers must come from the same filing period. Matching the wrong quarter can
            create a false relationship, so the project applies strict period rules.
          </p>
        }
        technical={
          <p>
            Same accession; duration bands and report-date tolerance for period integrity. Combined
            / pooled 10-K+10-Q correlations are exploratory only and are not the public ranking
            metric.
          </p>
        }
      />

      <Section
        id="correlation"
        title="Correlation overview"
        plain={
          <p>
            A relationship (correlation) answers: when tone is more positive, do earnings changes
            also tend to be stronger? Two related measures are shown. Spearman is primary; Pearson is
            secondary, because extreme earnings swings can distort a simple straight-line fit.
          </p>
        }
        technical={
          <p>
            Public primary: Spearman ρ on 10-Q NI. Secondary display: Pearson r with Fisher 95% CI
            when n is sufficient. See{" "}
            <a href="#spearman">Spearman</a> and <a href="#pearson">Pearson</a>.
          </p>
        }
      />

      <Section
        id="spearman"
        title="Spearman"
        plain={
          <p>
            Spearman measures whether more positive tone generally appears alongside stronger
            financial performance. It focuses on direction and is less affected by unusually large
            earnings changes. That is why Spearman is the primary public metric.
          </p>
        }
        technical={
          <p>
            Rank-based association between MD&amp;A tone and YoY net income for matched 10-Q
            observations.
          </p>
        }
      />

      <Section
        id="pearson"
        title="Pearson"
        plain={
          <p>
            Pearson measures the strength of a straight-line relationship. It can be more sensitive
            to unusually large earnings changes (for example, swings around near-zero prior income).
          </p>
        }
        technical={
          <p>
            Linear Pearson r with Fisher 95% confidence interval when sample size allows. Shown as
            secondary detail on company pages.
          </p>
        }
      />

      <Section
        id="agreement"
        title="Direction agreement"
        plain={
          <p>
            Agreement counts how often tone and earnings simply moved the same way (both up or both
            down). Near-neutral cases are excluded so tiny noise does not count as a “move.”
          </p>
        }
        technical={
          <p>
            Direction agreement after excluding near-neutral observations. Displayed as num / den
            (for example, 6 / 8).
          </p>
        }
      />

      <Section
        id="sample-size"
        title="Sample size"
        plain={
          <p>
            Sample size is how many comparable quarterly filings enter the estimate. More
            observations usually make the estimate steadier, but a larger sample is not automatic
            proof of an important relationship.
          </p>
        }
        technical={
          <ul className="prose-list">
            <li>n ≥ 10: more established sample (label only)</li>
            <li>n = 8–9: usable; included on the default board</li>
            <li>n = 6–7: limited; company page only</li>
            <li>n &lt; 6: insufficient for rankings</li>
          </ul>
        }
      />

      <Section
        id="p-values"
        title="p-values"
        plain={
          <p>
            The p-value measures how unusual a result this strong would be under a no-relationship
            assumption. Small p-values are a clue, not a verdict, especially when hundreds of
            companies are tested.
          </p>
        }
        technical={
          <p>
            Two-sided p-values for Spearman and Pearson appear in collapsed statistical details on
            company pages.
          </p>
        }
      />

      <Section
        id="fdr"
        title="FDR (multiple-testing adjustment)"
        plain={
          <>
            <p>
              When hundreds of companies are tested, some can appear statistically notable by chance.
              False Discovery Rate, or FDR, adjusts for that problem.
            </p>
            <div className="fdr-funnel" aria-label="FDR funnel illustration">
              <div className="fdr-step">
                <strong>{fmtCount(board)}</strong>
                <span>ranking-eligible companies tested</span>
              </div>
              <div className="fdr-arrow" aria-hidden="true">
                ↓
              </div>
              <div className="fdr-step">
                <strong>raw p &lt; .05</strong>
                <span>some look notable before adjustment</span>
              </div>
              <div className="fdr-arrow" aria-hidden="true">
                ↓
              </div>
              <div className="fdr-step highlight">
                <strong>{fmtCount(fdr)}</strong>
                <span>remain after multiple-testing adjustment (q &lt; .05)</span>
              </div>
            </div>
            <p>
              FDR helps reduce the chance that the leaderboard is highlighting random statistical
              flukes. It does <strong>not</strong> prove the {fmtCount(fdr)} survivors are
              economically important or causal.
            </p>
          </>
        }
        technical={
          <p>
            Benjamini–Hochberg q among ranking-eligible companies. Badge when q &lt; 0.05. Not proof
            or certainty.
          </p>
        }
      />

      <Section
        id="confidence-interval"
        title="Confidence intervals"
        plain={
          <p>
            The confidence interval shows a range of plausible values for the estimated relationship.
            Wider intervals mean more uncertainty. It is not a guaranteed range.
          </p>
        }
        technical={<p>Fisher 95% CI for Pearson r when n is sufficient.</p>}
      />

      <Section
        id="relationship-labels"
        title="Relationship labels"
        plain={
          <p>
            On the site, Spearman values are also described in everyday language (for example,
            “strong positive”). These labels describe statistical relationship strength only. They do not
            measure company quality, management credibility, or investment value.
          </p>
        }
        technical={
          <ul className="prose-list">
            <li>ρ ≥ 0.70: Strong positive</li>
            <li>0.40–0.69: Moderate positive</li>
            <li>0.20–0.39: Weak positive</li>
            <li>−0.19–0.19: Little or no relationship</li>
            <li>−0.39 to −0.20: Weak negative</li>
            <li>−0.69 to −0.40: Moderate negative</li>
            <li>ρ ≤ −0.70: Strong negative</li>
          </ul>
        }
      />

      <Section
        id="sector-weighting"
        title="Sector weighting"
        plain={
          <>
            <p>
              <strong>Typical filing.</strong> That is the filing-weighted result: every filing counts.
            </p>
            <p>
              <strong>Typical company.</strong> That is the company-balanced result: each company gets equal weight so large filers do not
              dominate.
            </p>
            <p>
              These two views can differ (Industrials is a useful example). Neither alone is the
              full story.
            </p>
          </>
        }
        technical={
          <p>
            Filing-weighted Spearman/Pearson and company-balanced Pearson on 10-Q NI. Winsorized
            Pearson shown when n≥20 for context.
          </p>
        }
      />

      <Section
        id="scatterplots"
        title="How to read scatterplots"
        plain={
          <ul className="prose-list">
            <li>Each dot represents one 10-Q filing</li>
            <li>Left–right (x): MD&amp;A tone (more negative ← → more positive)</li>
            <li>Up–down (y): year-over-year financial change</li>
            <li>Upper-right: more positive language with improving earnings</li>
            <li>Lower-left: more negative language with worsening earnings</li>
          </ul>
        }
        technical={
          <p>
            Primary company charts use 10-Q points only. Sector charts pool 10-Q filings for the
            industry.
          </p>
        }
      />

      <Section
        id="limitations"
        title="Limitations"
        plain={
          <ul className="prose-list">
            <li>Near-zero prior earnings and loss↔profit flips can inflate Pearson</li>
            <li>MD&amp;A extraction quality varies by filing layout</li>
            <li>Model averages are not a human reading of emphasis or risk language</li>
            <li>Sector filing-weighted vs company-balanced results can differ</li>
            <li>Annual (10-K) history remains short for many companies</li>
            <li>This site explores a same-filing relationship, not prediction</li>
          </ul>
        }
      />

      <p className="note">
        <Link href="/">← Overview</Link>
        {" · "}
        <Link href="/about">About this project</Link>
      </p>
      </div>
    </div>
  );
}
