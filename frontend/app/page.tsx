import Link from "next/link";
import CompanyBrowser from "@/components/CompanyBrowser";
import FdrBadge from "@/components/FdrBadge";
import MethodologyLink from "@/components/MethodologyLink";
import MiniScatter from "@/components/MiniScatter";
import StrengthBar from "@/components/StrengthBar";
import { CompanyRankTable } from "@/components/RankTables";
import { loadSiteData } from "@/lib/data";
import {
  agreementSentence,
  observationsPhrase,
  relationshipFromRho,
} from "@/lib/explain";
import { fmtCount, fmtR } from "@/lib/format";
import {
  formIs10Q,
  isDefaultEligible,
  isFdrSignificant,
  ni10q,
  sortCompanies,
} from "@/lib/phase5";
import { sectorSlug } from "@/lib/sector";
import type { CompanyStat, SectorStat } from "@/lib/types";

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

function FeaturedCaseGrid({ companies }: { companies: CompanyStat[] }) {
  const copy: Record<string, string> = {
    AAPL: "Management tone tended to become more positive when quarterly earnings improved.",
    ADI: "One of the stronger positive relationships in the published set.",
    AMZN: "Showed a moderate negative relationship, but the result did not survive the multiple-testing adjustment.",
    NVDA: "Tone and earnings moved in the same direction in all 13 comparable quarters.",
    ABBV: "Showed little relationship between MD&A tone and quarterly net income.",
  };
  const order = ["AAPL", "ADI", "AMZN", "NVDA", "ABBV"];
  const by = Object.fromEntries(companies.map((c) => [c.ticker, c]));
  const rows = order.map((t) => by[t]).filter(Boolean) as CompanyStat[];
  if (!rows.length) return null;

  return (
    <section className="section" aria-labelledby="stories-heading">
      <div className="section-head">
        <h2 id="stories-heading">Which companies illustrate the result?</h2>
        <p>
          A few educational examples: stronger relationships, results that do not survive the
          multiple-testing adjustment, and near-zero cases.
        </p>
      </div>
      <div className="story-grid">
        {rows.map((c) => {
          const ni = ni10q(c);
          const label = relationshipFromRho(ni.spearman_rho);
          const pts = (c.points ?? [])
            .filter((p) => formIs10Q(p.form) && p.sentiment != null && p.income_pct != null)
            .map((p) => ({
              sentiment: Number(p.sentiment),
              income: Number(p.income_pct) * 100,
            }));
          const agree = agreementSentence(ni.agree_num, ni.agree_den);
          return (
            <Link key={c.ticker} href={`/company/${c.ticker}`} className="story-card">
              <div className="story-top">
                <div>
                  <div className="story-ticker">{c.ticker}</div>
                  <div className="muted tiny">{c.name}</div>
                </div>
                {isFdrSignificant(c) ? <FdrBadge active compact interactive={false} /> : null}
              </div>
              <div className={`rel-label lg ${label.tone}`}>{label.short}</div>
              <StrengthBar rho={ni.spearman_rho} tone={label.tone} />
              <MiniScatter points={pts} />
              <p className="story-takeaway">{copy[c.ticker]}</p>
              <div className="story-meta muted tiny">
                Relationship strength: {fmtR(ni.spearman_rho)} · {observationsPhrase(ni.n)}
                {agree ? ` · Direction agreement: ${ni.agree_num}/${ni.agree_den}` : ""}
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

export default async function HomePage() {
  const { companies: companyRows, sectors: sectorRows, source } = await loadSiteData();

  const mostSectors = bySectorSpearman(sectorRows, "desc").slice(0, 4);
  const leastSectors = bySectorSpearman(sectorRows, "asc").slice(0, 2);
  const snapshotSectors = [
    ...mostSectors.slice(0, 3),
    ...leastSectors.filter((s) => !mostSectors.slice(0, 3).some((m) => m.sector === s.sector)),
  ].slice(0, 4);

  const eligible = sortCompanies(companyRows, "spearman", "desc");
  const mostCompanies = eligible.slice(0, 6);
  const leastCompanies = [...eligible].reverse().slice(0, 6);

  const ready = companyRows.filter(isDefaultEligible).length;
  const fdrN = companyRows.filter(isFdrSignificant).length;
  const analyzed = companyRows.reduce((n, c) => n + (c.n_filings || 0), 0);

  return (
    <>
      <section className="hero hero-impact">
        <div className="kicker">Accounting · SEC filings · language analysis</div>
        <h1>Does the tone match the numbers?</h1>
        <p className="lede hero-lede">
          This project tests whether the tone of management&apos;s MD&amp;A moves with changes in
          financial performance across {fmtCount(analyzed)} S&amp;P 500 10-K and 10-Q filings.
        </p>
        <div className="hero-stats">
          <div className="hero-stat">
            <div className="hero-stat-value">{fmtCount(analyzed)}</div>
            <div className="hero-stat-label">SEC filings analyzed</div>
          </div>
          <div className="hero-stat">
            <div className="hero-stat-value">{fmtCount(ready)}</div>
            <div className="hero-stat-label">Companies in the main comparison</div>
          </div>
          <div className="hero-stat hero-stat-fdr">
            <div className="hero-stat-value">{fmtCount(fdrN)}</div>
            <div className="hero-stat-label">
              Relationships remained statistically notable after adjusting for hundreds of tests
            </div>
            <MethodologyLink topic="fdr" className="meth-link">
              Why only {fdrN}?
            </MethodologyLink>
          </div>
        </div>
        <p className="note">
          The analysis measures a same-filing relationship, not a forecast.{" "}
          {source === "phase5_preview" ? "Preview data." : null}
        </p>
      </section>

      <section className="section pipeline-visual" aria-label="Research workflow">
        <div className="section-head">
          <h2>How the analysis works</h2>
          <p>From the filing text to the comparison with reported results.</p>
        </div>
        <ol className="flow-steps">
          <li>
            <span className="flow-title">SEC filing</span>
            <span className="flow-body">Company reports results</span>
          </li>
          <li>
            <span className="flow-title">MD&amp;A</span>
            <span className="flow-body">Management explains what happened</span>
          </li>
          <li>
            <span className="flow-title">Tone score</span>
            <span className="flow-body">Estimate how positive or negative the language is</span>
          </li>
          <li>
            <span className="flow-title">Financial results</span>
            <span className="flow-body">Match the reported numbers for the same period</span>
          </li>
          <li>
            <span className="flow-title">Comparison</span>
            <span className="flow-body">See whether tone and performance moved together</span>
          </li>
        </ol>
        <p className="pipeline-foot">
          <Link href="/methodology">View methodology</Link>
        </p>
      </section>

      <section className="section findings-visual" aria-labelledby="findings-heading">
        <div className="section-head">
          <h2 id="findings-heading">What did the analysis find?</h2>
          <p>
            Across the S&amp;P 500, most companies showed weak-to-moderate relationships between
            management tone and quarterly earnings. A smaller group showed stronger and more
            consistent patterns.
          </p>
        </div>
        <div className="findings-points">
          <article>
            <h3>Most relationships are modest</h3>
            <p>Tone and earnings usually do not move in tight lockstep.</p>
          </article>
          <article>
            <h3>
              {fdrN} of {ready} ranking-eligible relationships remain after multiple-testing
              adjustment
            </h3>
            <p>
              After adjusting for hundreds of company tests, a minority remain statistically
              notable. That is not the same as proof.{" "}
              <MethodologyLink topic="fdr">Why that matters</MethodologyLink>
            </p>
          </article>
          <article>
            <h3>Company results vary widely</h3>
            <p>
              Positive, negative, high-agreement, and near-zero examples all appear in the data.
            </p>
          </article>
        </div>
      </section>

      <FeaturedCaseGrid companies={companyRows} />

      <section className="section" id="explore" aria-labelledby="explore-heading">
        <div className="section-head row-head">
          <div>
            <h2 id="explore-heading">Company rankings</h2>
            <p>
              Default board: quarterly MD&amp;A tone vs net income, at least 8 observations,
              relationship strength first.
            </p>
          </div>
          <Link className="text-cta" href="#companies-board">
            View all {fmtCount(ready)} companies
          </Link>
        </div>
        <div className="rank-grid">
          <CompanyRankTable
            title="Strongest positive"
            rows={mostCompanies}
            empty="No eligible companies yet."
          />
          <CompanyRankTable
            title="Strongest negative"
            rows={leastCompanies}
            empty="No eligible companies yet."
          />
        </div>
      </section>

      <section className="section" aria-labelledby="sectors-heading">
        <div className="section-head row-head">
          <div>
            <h2 id="sectors-heading">Industry snapshots</h2>
            <p>A few contrasts between stronger and flatter industry patterns.</p>
          </div>
          <Link className="text-cta" href="/industries">
            See industry results
          </Link>
        </div>
        <div className="sector-snapshot-grid">
          {snapshotSectors.map((row) => {
            const rho =
              row.fw_spearman_rho_10q_ni ??
              row.primary_10q_ni?.filing_weighted_spearman_rho ??
              null;
            const cb =
              row.cb_pearson_r_10q_ni ?? row.primary_10q_ni?.company_balanced_pearson_r ?? null;
            return (
              <Link
                key={row.sector}
                href={`/industries/${sectorSlug(row.sector)}`}
                className="sector-snap-card"
              >
                <div className="story-ticker">{row.sector}</div>
                <div className="snap-row">
                  <span className="muted tiny">Typical filing</span>
                  <span className={`rel-label ${relationshipFromRho(rho).tone}`}>
                    {relationshipFromRho(rho).short}
                  </span>
                </div>
                <div className="snap-row">
                  <span className="muted tiny">Typical company</span>
                  <span className={`rel-label ${relationshipFromRho(cb).tone}`}>
                    {relationshipFromRho(cb).short}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="section cta-band" aria-labelledby="rigor-heading">
        <h2 id="rigor-heading">How careful is the method?</h2>
        <p>
          Period-matched filings, rank-based relationship measures, direction agreement, sample-size
          rules, and a multiple-testing adjustment, with limitations stated plainly.
        </p>
        <div className="cta-row">
          <Link className="btn-primary" href="/methodology">
            View methodology
          </Link>
          <Link className="btn-ghost" href="/about">
            About this project
          </Link>
        </div>
      </section>

      <div id="companies-board">
        <CompanyBrowser companies={companyRows} />
      </div>
    </>
  );
}
