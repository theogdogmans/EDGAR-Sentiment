import Link from "next/link";
import FdrBadge from "@/components/FdrBadge";
import MethodologyLink from "@/components/MethodologyLink";
import { fmtR, toneClass } from "@/lib/format";
import {
  agreementSentence,
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
    <div className="panel">
      <h2>{title}</h2>
      <p className="hint">
        Plain English first: filing-level view asks whether a typical filing shows a relationship;
        company-balanced asks about a typical company.{" "}
        <MethodologyLink topic="sector-weighting">Why are these different? →</MethodologyLink>
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
                    <div className="muted tiny">Spearman {fmtR(rho)}</div>
                  </td>
                  <td>
                    <div className={toneClass(cb)}>{relationshipFromRho(cb).short}</div>
                    <div className="muted tiny">Pearson {fmtR(cb)}</div>
                  </td>
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
        Default board: quarterly MD&amp;A tone vs net income, with enough observations (at least
        8). Sorted by the primary relationship measure. Not a forecast.
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
              <th>Detail</th>
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
      )}
    </div>
  );
}

export function CaseStudyCards({ companies }: { companies: CompanyStat[] }) {
  const blurb: Record<string, string> = {
    AAPL: "Strong positive relationship that survives the multiple-testing adjustment.",
    ADI: "Another strong relationship, with tone and earnings moving in the same direction in every eligible quarter.",
    AMZN: "Management tone and net income moved in opposite directions more often than many companies, but the relationship does not survive the multiple-testing adjustment.",
    NVDA: "Tone and earnings moved in the same direction in 13 of 13 eligible quarters, even though the overall correlation is less statistically convincing.",
    ABBV: "A useful example of little systematic relationship under the current period-matched rules — methodology choices matter.",
    ADSK: "Near-zero relationship under the current rules — a reminder that earlier pooled estimates can look different after stricter matching.",
  };
  const order = ["AAPL", "ADI", "AMZN", "NVDA", "ABBV"];
  const by = Object.fromEntries(companies.map((c) => [c.ticker, c]));
  const rows = order.map((t) => by[t]).filter(Boolean);
  if (!rows.length) return null;
  return (
    <div className="panel">
      <h2>Different companies tell different stories</h2>
      <p className="hint">
        Educational case studies from the full S&amp;P 500 analysis — including stronger
        relationships, informative non-survivors, and near-zero examples.
      </p>
      <div className="case-grid">
        {rows.map((c) => {
          const ni = ni10q(c);
          const label = relationshipFromRho(ni.spearman_rho);
          const agree = agreementSentence(ni.agree_num, ni.agree_den);
          return (
            <Link key={c.ticker} href={`/company/${c.ticker}`} className="case-card">
              <div className="case-ticker">{c.ticker}</div>
              <div className={`rel-label ${label.tone}`}>{label.short}</div>
              {isFdrSignificant(c) ? <FdrBadge active compact interactive={false} /> : null}
              <p>{blurb[c.ticker]}</p>
              <div className="case-stats muted tiny">
                Spearman {fmtR(ni.spearman_rho)} · {observationsPhrase(ni.n)}
                {agree ? ` · ${ni.agree_num}/${ni.agree_den} same direction` : ""}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
