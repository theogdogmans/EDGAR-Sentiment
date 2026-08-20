"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { fmtR, toneClass } from "@/lib/format";
import { sectorSlug } from "@/lib/sector";
import type { CompanyStat } from "@/lib/types";

export default function CompanyBrowser({ companies }: { companies: CompanyStat[] }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (!q) return companies;
    return companies.filter((row) =>
      [row.ticker, row.display, row.name, row.sector].join(" ").toUpperCase().includes(q)
    );
  }, [companies, query]);

  return (
    <div className="panel">
      <h2>Browse companies</h2>
      <p className="hint">Filter the S&amp;P 500 list. Scores come from the published aggregate cache.</p>
      <form className="search" onSubmit={(e) => e.preventDefault()}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter ticker, name, or sector"
          aria-label="Filter S&P 500"
        />
      </form>
      <p className="note">{filtered.length} companies</p>
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Company</th>
            <th>Sector</th>
            <th>r</th>
            <th>Scored</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((row) => (
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
              <td>{row.n_filings}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
