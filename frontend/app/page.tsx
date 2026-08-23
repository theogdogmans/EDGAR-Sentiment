import CompanyBrowser from "@/components/CompanyBrowser";
import { CaseStudyCards, CompanyRankTable, SectorRankTable } from "@/components/RankTables";
import { loadSiteData } from "@/lib/data";
import { isDefaultEligible, isFdrSignificant, sortCompanies } from "@/lib/phase5";
import type { SectorStat } from "@/lib/types";

export const revalidate = 3600;

function bySectorSpearman(rows: SectorStat[], dir: "desc" | "asc") {
  const scored = rows.filter((r) => {
    const rho =
      r.fw_spearman_rho_10q_ni ?? r.primary_10q_ni?.filing_weighted_spearman_rho ?? null;
    return rho != null;
  });
  scored.sort((a, b) => {
    const av =
      (a.fw_spearman_rho_10q_ni ??
        a.primary_10q_ni?.filing_weighted_spearman_rho ??
        0) as number;
    const bv =
      (b.fw_spearman_rho_10q_ni ??
        b.primary_10q_ni?.filing_weighted_spearman_rho ??
        0) as number;
    return dir === "desc" ? bv - av : av - bv;
  });
  return scored;
}

export default async function HomePage() {
  const { companies: companyRows, sectors: sectorRows, preload: status, source } =
    await loadSiteData();

  const mostSectors = bySectorSpearman(sectorRows, "desc").slice(0, 5);
  const leastSectors = bySectorSpearman(sectorRows, "asc").slice(0, 5);
  const eligible = sortCompanies(companyRows, "spearman", "desc");
  const mostCompanies = eligible.slice(0, 8);
  const leastCompanies = [...eligible].reverse().slice(0, 8);

  const ready = companyRows.filter(isDefaultEligible).length;
  const fdrN = companyRows.filter(isFdrSignificant).length;
  const analyzed = companyRows.reduce((n, c) => n + (c.n_filings || 0), 0);
  const empty = companyRows.length === 0;

  return (
    <>
      <section className="hero">
        <div className="kicker">S&amp;P 500 · 10-Q MD&amp;A vs Net Income YoY</div>
        <h1>Does the tone match the numbers?</h1>
        <p className="lede">
          Contemporaneous association between FinBERT-scored MD&amp;A tone and same-filing YoY
          net income. Primary company analysis is <strong>10-Q only</strong> (n≥8 public board,
          Spearman first). Most companies show weak-to-modest relationships; a minority are
          stronger and more consistent. Not a forecast.
        </p>
      </section>

      <div className="panel">
        <div className="kicker">{source === "phase5_preview" ? "Preview data" : "Published cache"}</div>
        <p style={{ margin: "8px 0 12px" }}>
          {status?.running
            ? status.message || "Worker running…"
            : status?.message ||
              (empty
                ? "Waiting for aggregates."
                : source === "phase5_preview"
                  ? "Loaded Phase 5A local preview payload."
                  : "Published aggregates loaded from Supabase.")}
        </p>
        <div className="progress">
          <div
            className="progress-bar"
            style={{
              width: `${Math.min(
                100,
                ready && companyRows.length
                  ? Math.round((ready / Math.max(companyRows.length, 1)) * 100)
                  : 0
              )}%`,
            }}
          />
        </div>
        <p className="note">
          {ready} companies on default board (n≥8) · {analyzed} filings in rollup · {fdrN} with
          FDR q&lt;.05
          {status?.current ? ` · last ${status.current}` : ""}
        </p>
      </div>

      <div className="stats">
        <div className="stat">
          <div className="label">Sectors</div>
          <div className="value">{sectorRows.length || "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Companies</div>
          <div className="value">{companyRows.length || "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Filings scored</div>
          <div className="value">{analyzed || "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Board (n≥8)</div>
          <div className="value">{ready || "—"}</div>
        </div>
      </div>

      <CaseStudyCards companies={companyRows} />

      <div className="rank-grid">
        <SectorRankTable
          title="Highest sector ρ (filing-weighted)"
          rows={mostSectors}
          empty="No sector associations yet."
        />
        <SectorRankTable
          title="Lowest sector ρ (filing-weighted)"
          rows={leastSectors}
          empty="No sector associations yet."
        />
      </div>

      <div className="rank-grid">
        <CompanyRankTable
          title="Highest Spearman ρ (n≥8)"
          rows={mostCompanies}
          empty="No eligible companies yet."
        />
        <CompanyRankTable
          title="Lowest Spearman ρ (n≥8)"
          rows={leastCompanies}
          empty="No eligible companies yet."
        />
      </div>

      <CompanyBrowser companies={companyRows} />
    </>
  );
}
