import Link from "next/link";
import { notFound } from "next/navigation";
import FdrBadge from "@/components/FdrBadge";
import MethodologyLink from "@/components/MethodologyLink";
import SentimentScatter from "@/components/SentimentScatter";
import { loadSiteData } from "@/lib/data";
import {
  observationsPhrase,
  relationshipFromRho,
} from "@/lib/explain";
import { fmtR, toneClass } from "@/lib/format";
import { formIs10Q, isFdrSignificant, ni10q, sortCompanies } from "@/lib/phase5";
import { findSectorBySlug, sectorSlug } from "@/lib/sector";

export const revalidate = 3600;

export default async function IndustryPage({
  params,
}: {
  params: Promise<{ sector: string }>;
}) {
  const { sector: slug } = await params;
  const { sectors: sectorList, companies } = await loadSiteData();
  const match = findSectorBySlug(sectorList, slug);
  if (!match) notFound();

  const p10 = match.primary_10q_ni;
  const fwRho = match.fw_spearman_rho_10q_ni ?? p10?.filing_weighted_spearman_rho ?? null;
  const fwR = match.fw_pearson_r_10q_ni ?? p10?.filing_weighted_pearson_r ?? null;
  const fwW = match.fw_winsor_r_10q_ni ?? p10?.winsorized_pearson_r ?? null;
  const fwN = match.fw_n_10q_ni ?? p10?.filing_n ?? match.n_income;
  const cbR = match.cb_pearson_r_10q_ni ?? p10?.company_balanced_pearson_r ?? null;
  const cbN = match.cb_n_companies_10q_ni ?? p10?.company_balanced_n_companies ?? null;
  const revOk = match.revenue_comparable !== false;
  const fwLabel = relationshipFromRho(fwRho);
  const cbLabel = relationshipFromRho(cbR);

  const members = sortCompanies(
    companies.filter((c) => c.sector === match.sector),
    "spearman",
    "desc"
  );

  const scatter = (match.points ?? [])
    .filter((p) => formIs10Q(p.form) && p.sentiment != null && p.income_pct != null)
    .map((p) => ({
      ticker: p.ticker,
      form: p.form,
      filed: p.filed,
      sentiment: Number((p.sentiment as number).toFixed(4)),
      income: Number(((p.income_pct as number) * 100).toFixed(2)),
    }));

  return (
    <>
      <p className="back">
        <Link href="/">← Overview</Link>
      </p>
      <section className="hero">
        <div className="kicker">Industry</div>
        <h1>{match.sector}</h1>
        <p className="lede">
          Across {match.n_companies} companies ({match.n_filings} scored filings), does management
          tone tend to move with quarterly earnings? Two complementary views are shown below.
        </p>
      </section>

      <div className="panel dual-weight">
        <h2>Two ways to read this industry</h2>
        <div className="dual-grid">
          <article>
            <h3>Does the typical filing show a relationship?</h3>
            <div className={`rel-label lg ${fwLabel.tone}`}>{fwLabel.short}</div>
            <p className="muted tiny">
              Filing-weighted · Spearman {fmtR(fwRho)} · {observationsPhrase(fwN)}
            </p>
          </article>
          <article>
            <h3>Does the typical company show a relationship?</h3>
            <div className={`rel-label lg ${cbLabel.tone}`}>{cbLabel.short}</div>
            <p className="muted tiny">
              Company-balanced · Pearson {fmtR(cbR)}
              {cbN != null ? ` · ${cbN} companies` : ""}
            </p>
          </article>
        </div>
        <p className="hint">
          These views can differ when a few large filers dominate.{" "}
          <MethodologyLink topic="sector-weighting">Why are these different? →</MethodologyLink>
        </p>
      </div>

      <details className="panel">
        <summary>
          <strong>Technical sector measures</strong>
        </summary>
        <table style={{ marginTop: 12 }}>
          <tbody>
            <tr>
              <th>Filing-weighted Spearman</th>
              <td className={toneClass(fwRho)}>{fmtR(fwRho)}</td>
            </tr>
            <tr>
              <th>Filing-weighted Pearson</th>
              <td className={toneClass(fwR)}>{fmtR(fwR)}</td>
            </tr>
            <tr>
              <th>Winsorized Pearson (when n≥20)</th>
              <td className={toneClass(fwW)}>{fmtR(fwW)}</td>
            </tr>
            <tr>
              <th>Company-balanced Pearson</th>
              <td className={toneClass(cbR)}>{fmtR(cbR)}</td>
            </tr>
            <tr>
              <th>Revenue</th>
              <td>
                {revOk
                  ? "Comparable revenue associations available as secondary on company pages."
                  : "Revenue comparison not used due to cross-company concept comparability."}
              </td>
            </tr>
          </tbody>
        </table>
      </details>

      <div className="panel">
        <h2>Quarterly filings in this industry</h2>
        <p className="hint">
          Each dot is one 10-Q.{" "}
          <MethodologyLink topic="scatterplots">How to read this chart →</MethodologyLink>
        </p>
        <SentimentScatter points={scatter} />
      </div>

      <div className="panel">
        <h2>Companies in {match.sector}</h2>
        <p className="hint">
          Members with enough quarterly observations, sorted by company-level relationship strength.
        </p>
        <div className="table-scroll">
          <table className="company-rank-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Relationship</th>
                <th>Sample</th>
                <th>Numbers</th>
              </tr>
            </thead>
            <tbody>
              {members.map((c) => {
                const ni = ni10q(c);
                const label = relationshipFromRho(ni.spearman_rho);
                return (
                  <tr key={c.ticker} className="row-link">
                    <td>
                      <Link href={`/company/${c.ticker}`}>{c.display || c.ticker}</Link>
                      <div className="muted tiny">{c.name}</div>
                      {isFdrSignificant(c) ? <FdrBadge active compact /> : null}
                    </td>
                    <td>
                      <div className={`rel-label ${label.tone}`}>{label.short}</div>
                    </td>
                    <td>{observationsPhrase(ni.n)}</td>
                    <td className="muted tiny">
                      Spearman {fmtR(ni.spearman_rho)}
                      <br />
                      Pearson {fmtR(ni.pearson_r)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="note">
        Other industries:{" "}
        {sectorList
          .filter((s) => s.sector !== match.sector)
          .slice(0, 8)
          .map((s, i) => (
            <span key={s.sector}>
              {i ? " · " : ""}
              <Link href={`/industries/${sectorSlug(s.sector)}`}>{s.sector}</Link>
            </span>
          ))}
      </p>
    </>
  );
}
