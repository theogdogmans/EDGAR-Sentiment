import Link from "next/link";
import { notFound } from "next/navigation";
import FdrBadge from "@/components/FdrBadge";
import MethodologyLink from "@/components/MethodologyLink";
import SentimentScatter from "@/components/SentimentScatter";
import StrengthBar from "@/components/StrengthBar";
import { loadSiteData } from "@/lib/data";
import { observationsPhrase, relationshipFromRho } from "@/lib/explain";
import { fmtCount, fmtR, toneClass } from "@/lib/format";
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
      sentiment: Number(p.sentiment),
      income: Number((p.income_pct as number) * 100),
      revenue: p.revenue_pct == null ? null : Number(p.revenue_pct) * 100,
    }));

  return (
    <>
      <p className="back">
        <Link href="/industries">← Industries</Link>
      </p>
      <section className="hero">
        <div className="kicker">Industry</div>
        <h1>{match.sector}</h1>
        <p className="lede">
          {fmtCount(match.n_companies)} companies · {fmtCount(match.n_filings)} scored filings
        </p>
      </section>

      <div className="dual-grid dual-hero">
        <article className="panel soft">
          <h3>Typical filing</h3>
          <div className={`rel-label display ${fwLabel.tone}`}>{fwLabel.short}</div>
          <StrengthBar rho={fwRho} tone={fwLabel.tone} />
          <p className="muted tiny">
            Filing-weighted · strength {fmtR(fwRho)} · {observationsPhrase(fwN, "quarterly")}
          </p>
        </article>
        <article className="panel soft">
          <h3>Typical company</h3>
          <div className={`rel-label display ${cbLabel.tone}`}>{cbLabel.short}</div>
          <StrengthBar rho={cbR} tone={cbLabel.tone} />
          <p className="muted tiny">
            Company-balanced · straight-line {fmtR(cbR)}
            {cbN != null ? ` · ${cbN} companies` : ""}
          </p>
        </article>
      </div>
      <p className="hint open-hint">
        The filing-weighted result gives more influence to companies with more filings. The
        company-balanced result gives each company equal weight.{" "}
        <MethodologyLink topic="sector-weighting">Why are these different?</MethodologyLink>
      </p>

      {!revOk ? (
        <div className="empty-state panel soft">
          <strong>Revenue comparison not used</strong>
          <p>
            Revenue comparison is not used for this industry because companies report revenue-like
            concepts differently.
          </p>
          <MethodologyLink topic="financial-data">Why?</MethodologyLink>
        </div>
      ) : null}

      <details className="panel soft">
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
          </tbody>
        </table>
      </details>

      <div className="panel soft chart-panel">
        <h2>Quarterly filings in this industry</h2>
        <p className="hint">
          Each dot represents one 10-Q filing.{" "}
          <MethodologyLink topic="scatterplots">How to read this chart</MethodologyLink>
        </p>
        <SentimentScatter points={scatter} />
      </div>

      <div className="panel soft">
        <h2>Companies in {match.sector}</h2>
        <div className="table-scroll">
          <table className="company-rank-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Relationship</th>
                <th>Sample</th>
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
                      <div className="muted tiny">Strength {fmtR(ni.spearman_rho)}</div>
                    </td>
                    <td>{observationsPhrase(ni.n)}</td>
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
