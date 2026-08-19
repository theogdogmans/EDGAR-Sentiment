"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

export type CompanyRow = {
  ticker: string;
  display: string | null;
  name: string;
  sector: string | null;
  filings_count: number;
  analyzed_count: number;
};

export default function CompanyList({ companies }: { companies: CompanyRow[] }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (!q) return companies;
    return companies.filter((row) =>
      [row.ticker, row.display, row.name, row.sector].join(" ").toUpperCase().includes(q)
    );
  }, [companies, query]);

  return (
    <>
      <form className="search" onSubmit={(e) => e.preventDefault()}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter ticker, name, or sector"
          aria-label="Filter S&P 500"
        />
      </form>
      <section className="panel">
        <h2>{filtered.length} companies</h2>
        <p className="hint">Ready means at least three filings are already scored.</p>
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Company</th>
              <th>Sector</th>
              <th>Scored</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const ready = (row.analyzed_count || 0) >= 3;
              return (
                <tr key={row.ticker} className="row-link">
                  <td>
                    <Link href={`/company/${row.ticker}`}>
                      <b>{row.display || row.ticker}</b>
                    </Link>
                  </td>
                  <td>
                    <Link href={`/company/${row.ticker}`}>{row.name}</Link>
                  </td>
                  <td className="muted">{row.sector || "—"}</td>
                  <td>
                    {row.analyzed_count || 0}/{row.filings_count || 0}
                  </td>
                  <td>
                    {ready ? <span className="pos">Ready</span> : <span className="muted">Caching</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </>
  );
}
