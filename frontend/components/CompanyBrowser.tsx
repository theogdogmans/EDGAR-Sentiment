"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { fmtAgreePct, fmtQ, fmtR, toneClass } from "@/lib/format";
import {
  filterCompanies,
  isDefaultEligible,
  isFdrSignificant,
  ni10q,
  sortCompanies,
  type LeaderboardFilter,
  type LeaderboardSort,
} from "@/lib/phase5";
import { sectorSlug } from "@/lib/sector";
import type { CompanyStat } from "@/lib/types";

export default function CompanyBrowser({ companies }: { companies: CompanyStat[] }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<LeaderboardSort>("spearman");
  const [filter, setFilter] = useState<LeaderboardFilter>("all");
  const [showLimited, setShowLimited] = useState(false);

  const board = useMemo(() => {
    let rows = showLimited
      ? companies.filter((c) => isDefaultEligible(c) || (c.ranking_eligible_limited ?? false))
      : companies.filter(isDefaultEligible);
    rows = filterCompanies(rows, filter);
    const q = query.trim().toUpperCase();
    if (q) {
      rows = rows.filter((row) =>
        [row.ticker, row.display, row.name, row.sector].join(" ").toUpperCase().includes(q)
      );
    }
    return sortCompanies(rows, sort, "desc");
  }, [companies, query, sort, filter, showLimited]);

  return (
    <div className="panel">
      <h2>Company leaderboard</h2>
      <p className="hint">
        Primary analysis: <strong>10-Q MD&amp;A tone vs Net Income YoY</strong>. Default board
        requires n≥8. Sorted by Spearman ρ first. Not predictive.
      </p>
      <div className="leaderboard-controls">
        <form className="search" onSubmit={(e) => e.preventDefault()}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter ticker, name, or sector"
            aria-label="Filter companies"
          />
        </form>
        <label>
          Sort{" "}
          <select value={sort} onChange={(e) => setSort(e.target.value as LeaderboardSort)}>
            <option value="spearman">Spearman ρ</option>
            <option value="pearson">Pearson r</option>
            <option value="agreement">Agreement</option>
            <option value="n">n</option>
            <option value="q">FDR q</option>
          </select>
        </label>
        <label>
          Filter{" "}
          <select value={filter} onChange={(e) => setFilter(e.target.value as LeaderboardFilter)}>
            <option value="all">All (n≥8)</option>
            <option value="fdr">FDR q&lt;.05</option>
            <option value="positive">Positive ρ</option>
            <option value="negative">Negative ρ</option>
            <option value="high_agreement">High agreement</option>
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={showLimited}
            onChange={(e) => setShowLimited(e.target.checked)}
          />{" "}
          Include limited sample (n=6–7)
        </label>
      </div>
      <p className="note">{board.length} companies on board</p>
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Company</th>
            <th>Sector</th>
            <th>ρ</th>
            <th>r</th>
            <th>Agree</th>
            <th>n</th>
            <th>q</th>
          </tr>
        </thead>
        <tbody>
          {board.map((row) => {
            const ni = ni10q(row);
            return (
              <tr key={row.ticker} className="row-link">
                <td>
                  <Link href={`/company/${row.ticker}`}>{row.display || row.ticker}</Link>
                  {isFdrSignificant(row) ? <span className="badge-fdr"> FDR</span> : null}
                </td>
                <td>{row.name}</td>
                <td>
                  {row.sector ? (
                    <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td className={toneClass(ni.spearman_rho)}>{fmtR(ni.spearman_rho)}</td>
                <td className={toneClass(ni.pearson_r)}>{fmtR(ni.pearson_r)}</td>
                <td>
                  {ni.agree_label ?? (ni.agree_pct != null ? fmtAgreePct(ni.agree_pct) : "—")}
                </td>
                <td>{ni.n || "—"}</td>
                <td>{fmtQ(ni.fdr_q)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
