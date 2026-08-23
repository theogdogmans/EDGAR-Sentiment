import Link from "next/link";
import CompanyBrowser from "@/components/CompanyBrowser";
import MethodologyLink from "@/components/MethodologyLink";
import { CaseStudyCards, CompanyRankTable, SectorRankTable } from "@/components/RankTables";
import { loadSiteData } from "@/lib/data";
import { isDefaultEligible, isFdrSignificant, sortCompanies } from "@/lib/phase5";
import type { SectorStat } from "@/lib/types";

export const revalidate = 3600;

function bySectorSpearman(rows: SectorStat[], dir: "desc" | "asc") {
  const scored = rows.filter((r) => {
    const rho =
      r.fw_spearman_rho_10q_ni ?? r.primary_10q_ni?.filing_weighted_spearman_rho ?? null;
    return rho != null;
  });
  scored.sort((a, b) => {
    const av =
      (a.fw_spearman_rho_10q_ni ??
        a.primary_10q_ni?.filing_weighted_spearman_rho ??
        0) as number;
    const bv =
      (b.fw_spearman_rho_10q_ni ??
        b.primary_10q_ni?.filing_weighted_spearman_rho ??
        0) as number;
    return dir === "desc" ? bv - av : av - bv;
  });
  return scored;
}

export default async function HomePage() {
  const { companies: companyRows, sectors: sectorRows, source } = await loadSiteData();

  const mostSectors = bySectorSpearman(sectorRows, "desc").slice(0, 5);
  const leastSectors = bySectorSpearman(sectorRows, "asc").slice(0, 5);
  const eligible = sortCompanies(companyRows, "spearman", "desc");
  const mostCompanies = eligible.slice(0, 8);
  const leastCompanies = [...eligible].reverse().slice(0, 8);

  const ready = companyRows.filter(isDefaultEligible).length;
  const fdrN = companyRows.filter(isFdrSignificant).length;
  const analyzed = companyRows.reduce((n, c) => n + (c.n_filings || 0), 0);

  return (
    <>
      <section className="hero">
        <div className="kicker">S&amp;P 500 accounting · language research</div>
        <h1>Does the tone match the numbers?</h1>
        <p className="lede">
          I analyzed {analyzed.toLocaleString()} S&amp;P 500 10-K and 10-Q filings to see whether
          the tone of management&apos;s MD&amp;A moves with changes in company performance. This is
          a contemporaneous comparison — not a forecast.
        </p>
      </section>

      <section className="panel pipeline" aria-label="Analysis pipeline">
        <h2>How the analysis works</h2>
        <ol className="pipeline-steps">
          <li>
            <strong>SEC filing</strong>
            <span>Pull each company&apos;s 10-K and 10-Q.</span>
          </li>
          <li>
            <strong>MD&amp;A section</strong>
            <span>Focus on where management explains company performance.</span>
          </li>
          <li>
            <strong>Measure tone</strong>
            <span>
              Use a finance-trained language model to estimate whether the language is positive,
              neutral, or negative.
            </span>
          </li>
          <li>
            <strong>Financial results</strong>
            <span>Match the filing to the correct quarterly net income and revenue figures.</span>
          </li>
          <li>
            <strong>Compare</strong>
            <span>
              Test whether changes in management tone move with changes in financial performance.
            </span>
          </li>
        </ol>
        <p className="pipeline-foot">
          <Link href="/methodology">See full methodology →</Link>
        </p>
      </section>

      <section className="panel findings" aria-labelledby="findings-heading">
        <h2 id="findings-heading">What did the analysis find?</h2>
        <p className="findings-lede">
          Across the S&amp;P 500, management tone usually had only a weak-to-moderate relationship
          with quarterly earnings. A smaller group of companies showed stronger and more consistent
          relationships.
        </p>
        <div className="stats findings-stats">
          <div className="stat">
            <div className="value">{analyzed.toLocaleString()}</div>
            <div className="label">Filings analyzed</div>
          </div>
          <div className="stat">
            <div className="value">{ready.toLocaleString()}</div>
            <div className="label">Companies with enough quarterly observations for the main comparison</div>
          </div>
          <div className="stat">
            <div className="value">{fdrN.toLocaleString()}</div>
            <div className="label">
              Companies whose relationship remained statistically notable after adjusting for
              hundreds of tests
            </div>
            <MethodologyLink topic="fdr" className="meth-link block-link">
              Why only {fdrN}? →
            </MethodologyLink>
          </div>
        </div>
        {source === "phase5_preview" ? (
          <p className="note">Preview data — not the live Supabase publish.</p>
        ) : null}
      </section>

      <section className="panel howto" aria-labelledby="howto-heading">
        <h2 id="howto-heading">How to read this site</h2>
        <div className="howto-grid">
          <article className="howto-card">
            <h3>Tone</h3>
            <p>How positive or negative management&apos;s MD&amp;A language is.</p>
            <MethodologyLink topic="sentiment-score">Learn more →</MethodologyLink>
          </article>
          <article className="howto-card">
            <h3>Earnings change</h3>
            <p>How net income changed compared with the same quarter one year earlier.</p>
            <MethodologyLink topic="financial-data">Learn more →</MethodologyLink>
          </article>
          <article className="howto-card">
            <h3>Relationship</h3>
            <p>Whether more positive language tends to occur alongside stronger earnings.</p>
            <MethodologyLink topic="correlation">Learn more →</MethodologyLink>
          </article>
          <article className="howto-card">
            <h3>Agreement</h3>
            <p>How often tone and earnings simply moved in the same direction.</p>
            <MethodologyLink topic="agreement">Learn more →</MethodologyLink>
          </article>
          <article className="howto-card">
            <h3>Statistical check</h3>
            <p>
              Whether the relationship still stands out after accounting for the hundreds of
              companies tested.
            </p>
            <MethodologyLink topic="fdr">Learn more →</MethodologyLink>
          </article>
        </div>
      </section>

      <CaseStudyCards companies={companyRows} />

      <div className="rank-grid">
        <SectorRankTable
          title="Industries with stronger filing-level relationships"
          rows={mostSectors}
          empty="No sector associations yet."
        />
        <SectorRankTable
          title="Industries with weaker filing-level relationships"
          rows={leastSectors}
          empty="No sector associations yet."
        />
      </div>

      <div className="rank-grid">
        <CompanyRankTable
          title="Strongest positive relationships"
          rows={mostCompanies}
          empty="No eligible companies yet."
        />
        <CompanyRankTable
          title="Strongest negative relationships"
          rows={leastCompanies}
          empty="No eligible companies yet."
        />
      </div>

      <CompanyBrowser companies={companyRows} />
    </>
  );
}
