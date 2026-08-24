import Link from "next/link";
import FdrBadge from "@/components/FdrBadge";
import MethodologyLink from "@/components/MethodologyLink";
import StrengthBar from "@/components/StrengthBar";
import { fmtR, toneClass } from "@/lib/format";
import {
  observationsPhrase,
  relationshipFromRho,
} from "@/lib/explain";
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
    <div className="panel soft">
      <h2>{title}</h2>
      <p className="hint">
        Typical filing vs typical company.{" "}
        <MethodologyLink topic="sector-weighting">Why are these different?</MethodologyLink>
      </p>
      {!rows.length ? (
        <p className="muted">{empty}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Industry</th>
              <th>Typical filing</th>
              <th>Typical company</th>
              <th>Filings</th>
              <th>Companies</th>
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
              const fwLabel = relationshipFromRho(rho);
              return (
                <tr key={row.sector} className="row-link">
                  <td>
                    <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
                  </td>
                  <td>
                    <div className={toneClass(rho)}>{fwLabel.short}</div>
                    <div className="muted tiny">Strength {fmtR(rho)}</div>
                  </td>
                  <td>
                    <div className={toneClass(cb)}>{relationshipFromRho(cb).short}</div>
                    <div className="muted tiny">Straight-line {fmtR(cb)}</div>
                  </td>
                  <td>{n || "n/a"}</td>
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
    <div className="panel soft">
      <h2>{title}</h2>
      <p className="hint">
        Quarterly tone vs net income · at least 8 observations · relationship strength first.
      </p>
      {!rows.length ? (
        <p className="muted">{empty}</p>
      ) : (
        <table className="company-rank-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Relationship</th>
              <th>Sample</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const ni = ni10q(row);
              const label = relationshipFromRho(ni.spearman_rho);
              return (
                <tr key={row.ticker} className="row-link">
                  <td>
                    <Link href={`/company/${row.ticker}`}>{row.display || row.ticker}</Link>
                    <div className="muted tiny">{row.name}</div>
                    {isFdrSignificant(row) ? <FdrBadge active compact /> : null}
                  </td>
                  <td>
                    <div className={`rel-label ${label.tone}`}>{label.short}</div>
                    <StrengthBar rho={ni.spearman_rho} tone={label.tone} />
                    <div className="muted tiny">Strength {fmtR(ni.spearman_rho)}</div>
                  </td>
                  <td>{observationsPhrase(ni.n)}</td>
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
  // Kept for compatibility; homepage uses FeaturedCaseGrid.
  void companies;
  return null;
}
