import Link from "next/link";
import { fmtAgreePct, fmtQ, fmtR, toneClass } from "@/lib/format";
import { isFdrSignificant, ni10q } from "@/lib/phase5";
import { sectorSlug } from "@/lib/sector";
import type { CompanyStat, SectorStat } from "@/lib/types";

export function SectorRankTable({
  rows,
  title,
  empty,
}: {
  rows: SectorStat[];
  title: string;
  empty: string;
}) {
  return (
    <div className="panel">
      <h2>{title}</h2>
      <p className="hint">
        Sector view shows filing-weighted Spearman ρ for 10-Q MD&amp;A tone vs net income YoY.
        Company-balanced Pearson is shown for context — do not reduce sectors to one number.
      </p>
      {!rows.length ? (
        <p className="muted">{empty}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Sector</th>
              <th title="Filing-weighted Spearman">ρ (FW)</th>
              <th title="Company-balanced Pearson">r (CB)</th>
              <th>Filings</th>
              <th>Cos.</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const rho =
                row.fw_spearman_rho_10q_ni ??
                row.primary_10q_ni?.filing_weighted_spearman_rho ??
                null;
              const cb =
                row.cb_pearson_r_10q_ni ??
                row.primary_10q_ni?.company_balanced_pearson_r ??
                null;
              const n =
                row.fw_n_10q_ni ?? row.primary_10q_ni?.filing_n ?? row.n_income ?? 0;
              return (
                <tr key={row.sector} className="row-link">
                  <td>
                    <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
                  </td>
                  <td className={toneClass(rho)}>{fmtR(rho)}</td>
                  <td className={toneClass(cb)}>{fmtR(cb)}</td>
                  <td>{n || "—"}</td>
                  <td>{row.n_companies}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function CompanyRankTable({
  rows,
  title,
  empty,
}: {
  rows: CompanyStat[];
  title: string;
  empty: string;
}) {
  return (
    <div className="panel">
      <h2>{title}</h2>
      <p className="hint">
        Default board: 10-Q NI only, n≥8, sorted by Spearman ρ. Contemporaneous same-filing
        association — not a forecast.
      </p>
      {!rows.length ? (
        <p className="muted">{empty}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Company</th>
              <th>ρ</th>
              <th>r</th>
              <th>n</th>
              <th>q</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const ni = ni10q(row);
              return (
                <tr key={row.ticker} className="row-link">
                  <td>
                    <Link href={`/company/${row.ticker}`}>{row.display || row.ticker}</Link>
                    {isFdrSignificant(row) ? (
                      <span className="badge-fdr" title="FDR q < 0.05 among ranking-eligible companies">
                        {" "}
                        FDR
                      </span>
                    ) : null}
                  </td>
                  <td>{row.name}</td>
                  <td className={toneClass(ni.spearman_rho)}>{fmtR(ni.spearman_rho)}</td>
                  <td className={toneClass(ni.pearson_r)}>{fmtR(ni.pearson_r)}</td>
                  <td>{ni.n || "—"}</td>
                  <td>{fmtQ(ni.fdr_q)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function CaseStudyCards({ companies }: { companies: CompanyStat[] }) {
  const blurb: Record<string, string> = {
    AAPL: "Strong positive 10-Q NI association; FDR-surviving.",
    ADI: "Strong positive 10-Q NI association; FDR-surviving.",
    AMZN: "Negative association; raw p significant, does not survive FDR.",
    MSFT: "Moderate/strong positive; does not survive FDR.",
    NVDA: "Unusually high direction agreement (13/13); correlation not FDR.",
  };
  const order = ["AAPL", "ADI", "AMZN", "MSFT", "NVDA"];
  const by = Object.fromEntries(companies.map((c) => [c.ticker, c]));
  const rows = order.map((t) => by[t]).filter(Boolean);
  if (!rows.length) return null;
  return (
    <div className="panel">
      <h2>Case studies</h2>
      <p className="hint">
        Featured names from the full S&amp;P 500 Phase 4 analysis — including FDR survivors and
        informative non-survivors.
      </p>
      <div className="case-grid">
        {rows.map((c) => {
          const ni = ni10q(c);
          return (
            <Link key={c.ticker} href={`/company/${c.ticker}`} className="case-card">
              <div className="case-ticker">
                {c.ticker}
                {isFdrSignificant(c) ? <span className="badge-fdr">FDR-adjusted significance</span> : null}
              </div>
              <div className="case-stats">
                ρ {fmtR(ni.spearman_rho)} · r {fmtR(ni.pearson_r)} · n={ni.n}
                {ni.agree_label ? ` · agree ${ni.agree_label}` : ""}
              </div>
              <p>{blurb[c.ticker]}</p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

/** Compact agreement display helper exported for tables */
export function agreeCell(c: CompanyStat): string {
  const ni = ni10q(c);
  if (ni.agree_label) return ni.agree_label;
  if (ni.agree_pct != null) return fmtAgreePct(ni.agree_pct);
  return "—";
}
