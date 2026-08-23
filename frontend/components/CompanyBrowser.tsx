"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import FdrBadge from "@/components/FdrBadge";
import MethodologyLink from "@/components/MethodologyLink";
import { fmtR } from "@/lib/format";
import {
  observationsPhrase,
  relationshipFromRho,
} from "@/lib/explain";
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
    <div className="panel" id="companies">
      <h2>Company leaderboard</h2>
      <p className="hint">
        Each row answers: for this company, does quarterly management tone tend to move with
        quarterly net income? Default board requires at least 8 quarterly observations.{" "}
        <MethodologyLink topic="sample-size">Why sample size matters →</MethodologyLink>
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
            <option value="spearman">Relationship (Spearman)</option>
            <option value="pearson">Straight-line (Pearson)</option>
            <option value="agreement">Direction agreement</option>
            <option value="n">Sample size</option>
            <option value="q">Multiple-testing q</option>
          </select>
        </label>
        <label>
          Filter{" "}
          <select value={filter} onChange={(e) => setFilter(e.target.value as LeaderboardFilter)}>
            <option value="all">All (enough observations)</option>
            <option value="fdr">Survives multiple-testing adjustment</option>
            <option value="positive">Positive relationship</option>
            <option value="negative">Negative relationship</option>
            <option value="high_agreement">High direction agreement</option>
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
      <p className="note">{board.length} companies on board</p>
      <div className="table-scroll">
        <table className="company-rank-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Industry</th>
              <th>Relationship</th>
              <th>Sample</th>
              <th>Numbers</th>
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
                    {isFdrSignificant(row) ? <FdrBadge active compact /> : null}
                  </td>
                  <td>
                    {row.sector ? (
                      <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
                    ) : (
                      "—"
                    )}
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
      </div>
    </div>
  );
}
