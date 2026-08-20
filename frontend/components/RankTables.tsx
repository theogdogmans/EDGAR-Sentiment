import Link from "next/link";
import { fmtPct, fmtR, toneClass } from "@/lib/format";
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
        Pooled Pearson r: MD&amp;A FinBERT score vs same-filing YoY net income. Industry
        samples are stronger than single-company n≈8.
      </p>
      {!rows.length ? (
        <p className="muted">{empty}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Sector</th>
              <th>r (income)</th>
              <th>n</th>
              <th>Agree</th>
              <th>Companies</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.sector} className="row-link">
                <td>
                  <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
                </td>
                <td className={toneClass(row.r_income)}>{fmtR(row.r_income)}</td>
                <td>{row.n_income || "—"}</td>
                <td>{fmtPct(row.agreement_income)}</td>
                <td>{row.n_companies}</td>
              </tr>
            ))}
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
        Company-level r uses few filings — treat as illustration, not a trading signal.
      </p>
      {!rows.length ? (
        <p className="muted">{empty}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Company</th>
              <th>Sector</th>
              <th>r (income)</th>
              <th>n</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.ticker} className="row-link">
                <td>
                  <Link href={`/company/${row.ticker}`}>{row.display || row.ticker}</Link>
                </td>
                <td>{row.name}</td>
                <td>
                  {row.sector ? (
                    <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td className={toneClass(row.r_income)}>{fmtR(row.r_income)}</td>
                <td>{row.n_income || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
