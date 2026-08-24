"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import FdrBadge from "@/components/FdrBadge";
import MethodologyLink from "@/components/MethodologyLink";
import StrengthBar from "@/components/StrengthBar";
import { fmtR } from "@/lib/format";
import { observationsPhrase, relationshipFromRho } from "@/lib/explain";
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
  const [sector, setSector] = useState("all");
  const [showLimited, setShowLimited] = useState(false);

  const sectors = useMemo(() => {
    const s = new Set(companies.map((c) => c.sector).filter(Boolean) as string[]);
    return [...s].sort();
  }, [companies]);

  const board = useMemo(() => {
    let rows = showLimited
      ? companies.filter((c) => isDefaultEligible(c) || (c.ranking_eligible_limited ?? false))
      : companies.filter(isDefaultEligible);
    rows = filterCompanies(rows, filter);
    if (sector !== "all") rows = rows.filter((r) => r.sector === sector);
    const q = query.trim().toUpperCase();
    if (q) {
      rows = rows.filter((row) =>
        [row.ticker, row.display, row.name, row.sector].join(" ").toUpperCase().includes(q)
      );
    }
    return sortCompanies(rows, sort, "desc");
  }, [companies, query, sort, filter, showLimited, sector]);

  return (
    <section className="section panel soft" id="companies" aria-labelledby="board-heading">
      <div className="section-head">
        <h2 id="board-heading">All companies on the main board</h2>
        <p>
          Does quarterly management tone tend to move with quarterly net income?{" "}
          <MethodologyLink topic="sample-size">Why sample size matters</MethodologyLink>
        </p>
      </div>
      <div className="leaderboard-controls">
        <form className="search" onSubmit={(e) => e.preventDefault()}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search ticker, name, or sector"
            aria-label="Filter companies"
          />
        </form>
        <label>
          Show{" "}
          <select value={filter} onChange={(e) => setFilter(e.target.value as LeaderboardFilter)}>
            <option value="all">All</option>
            <option value="positive">Strongest positive</option>
            <option value="negative">Strongest negative</option>
            <option value="fdr">Survives multiple-testing adjustment</option>
            <option value="high_agreement">High agreement</option>
          </select>
        </label>
        <label>
          Sector{" "}
          <select value={sector} onChange={(e) => setSector(e.target.value)}>
            <option value="all">All sectors</option>
            {sectors.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sort{" "}
          <select value={sort} onChange={(e) => setSort(e.target.value as LeaderboardSort)}>
            <option value="spearman">Relationship strength</option>
            <option value="agreement">Direction agreement</option>
            <option value="n">Sample size</option>
            <option value="q">Multiple-testing q</option>
            <option value="pearson">Straight-line (Pearson)</option>
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={showLimited}
            onChange={(e) => setShowLimited(e.target.checked)}
          />{" "}
          Include limited sample (6–7 quarters)
        </label>
      </div>
      <p className="note">{board.length} companies shown</p>
      <div className="table-scroll">
        <table className="company-rank-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Industry</th>
              <th>Relationship</th>
              <th>Sample</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {board.map((row) => {
              const ni = ni10q(row);
              const label = relationshipFromRho(ni.spearman_rho);
              return (
                <tr key={row.ticker} className="row-link">
                  <td>
                    <Link href={`/company/${row.ticker}`}>{row.display || row.ticker}</Link>
                    <div className="muted tiny">{row.name}</div>
                  </td>
                  <td>
                    {row.sector ? (
                      <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
                    ) : (
                      "n/a"
                    )}
                  </td>
                  <td>
                    <div className={`rel-label ${label.tone}`}>{label.short}</div>
                    <StrengthBar rho={ni.spearman_rho} tone={label.tone} />
                    <div className="muted tiny">Strength {fmtR(ni.spearman_rho)}</div>
                  </td>
                  <td>{observationsPhrase(ni.n)}</td>
                  <td>{isFdrSignificant(row) ? <FdrBadge active compact /> : <span className="muted tiny">n/a</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
