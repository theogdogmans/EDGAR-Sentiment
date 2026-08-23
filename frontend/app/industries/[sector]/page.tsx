import Link from "next/link";
import { notFound } from "next/navigation";
import SentimentScatter from "@/components/SentimentScatter";
import { loadSiteData } from "@/lib/data";
import { fmtPct, fmtR, fmtScore, toneClass } from "@/lib/format";
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
        <Link href="/">← Rankings</Link>
      </p>
      <section className="hero">
        <div className="kicker">Industry · 10-Q NI</div>
        <h1>{match.sector}</h1>
        <p className="lede">
          Dual-weight view of contemporaneous MD&amp;A tone vs YoY net income across{" "}
          {match.n_companies} companies ({match.n_filings} scored filings). Filing-weighted and
          company-balanced results can differ — neither alone is the full story.
        </p>
      </section>

      <div className="stats">
        <div className="stat">
          <div className="label">FW Spearman ρ</div>
          <div className={`value ${toneClass(fwRho)}`}>{fmtR(fwRho)}</div>
        </div>
        <div className="stat">
          <div className="label">FW Pearson r</div>
          <div className={`value ${toneClass(fwR)}`}>{fmtR(fwR)}</div>
        </div>
        <div className="stat">
          <div className="label">Company-balanced r</div>
          <div className={`value ${toneClass(cbR)}`}>{fmtR(cbR)}</div>
        </div>
        <div className="stat">
          <div className="label">Filings / cos.</div>
          <div className="value">
            {fwN || "—"}
            <span className="muted" style={{ fontSize: "0.45em", display: "block" }}>
              {cbN != null ? `${cbN} balanced` : ""}
            </span>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Weighting detail</h2>
        <table>
          <tbody>
            <tr>
              <th>Filing-weighted Pearson</th>
              <td className={toneClass(fwR)}>{fmtR(fwR)}</td>
            </tr>
            <tr>
              <th>Filing-weighted Spearman</th>
              <td className={toneClass(fwRho)}>{fmtR(fwRho)}</td>
            </tr>
            <tr>
              <th>Winsorized Pearson (n≥20)</th>
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
                  ? "Comparable revenue associations available as secondary."
                  : "Revenue comparison not used due to cross-company concept comparability."}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>10-Q scatter (filing-weighted pool)</h2>
        <p className="hint">Each point is one 10-Q filing. n = {fwN || "—"}.</p>
        <SentimentScatter points={scatter} />
      </div>

      <div className="panel">
        <h2>Companies in {match.sector}</h2>
        <p className="hint">
          Default-eligible members sorted by company 10-Q Spearman ρ (n≥8). Limited-sample names
          appear on company pages only.
        </p>
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th>ρ</th>
              <th>r</th>
              <th>n</th>
              <th>Agree</th>
            </tr>
          </thead>
          <tbody>
            {members.map((c) => {
              const ni = ni10q(c);
              return (
                <tr key={c.ticker} className="row-link">
                  <td>
                    <Link href={`/company/${c.ticker}`}>{c.display || c.ticker}</Link>
                    {isFdrSignificant(c) ? <span className="badge-fdr"> FDR</span> : null}
                  </td>
                  <td>{c.name}</td>
                  <td className={toneClass(ni.spearman_rho)}>{fmtR(ni.spearman_rho)}</td>
                  <td className={toneClass(ni.pearson_r)}>{fmtR(ni.pearson_r)}</td>
                  <td>{ni.n || "—"}</td>
                  <td>{ni.agree_label ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
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
