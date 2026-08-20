import CompanyBrowser from "@/components/CompanyBrowser";
import { CompanyRankTable, SectorRankTable } from "@/components/RankTables";
import { createSupabaseClient } from "@/lib/supabase";
import type { CompanyStat, PreloadStatus, SectorStat } from "@/lib/types";

export const revalidate = 3600;

function byIncomeR(rows: SectorStat[] | CompanyStat[], dir: "desc" | "asc") {
  const scored = rows.filter((r) => r.r_income != null && (r.n_income || 0) >= 3);
  scored.sort((a, b) => {
    const av = a.r_income as number;
    const bv = b.r_income as number;
    return dir === "desc" ? bv - av : av - bv;
  });
  return scored;
}

export default async function HomePage() {
  const supabase = createSupabaseClient();
  const [{ data: sectors }, { data: companies }, { data: preload }] = await Promise.all([
    supabase.from("sector_stats").select("*").order("sector"),
    supabase.from("company_stats").select("*").order("ticker"),
    supabase
      .from("preload_status")
      .select("running, stage, current, message, coverage")
      .eq("id", 1)
      .maybeSingle(),
  ]);

  const sectorRows = (sectors ?? []) as SectorStat[];
  const companyRows = (companies ?? []) as CompanyStat[];
  const status = (preload as PreloadStatus | null) ?? null;
  const coverage = status?.coverage ?? null;

  const mostSectors = byIncomeR(sectorRows, "desc").slice(0, 5) as SectorStat[];
  const leastSectors = byIncomeR(sectorRows, "asc").slice(0, 5) as SectorStat[];
  const mostCompanies = byIncomeR(companyRows, "desc").slice(0, 8) as CompanyStat[];
  const leastCompanies = byIncomeR(companyRows, "asc").slice(0, 8) as CompanyStat[];

  const ready = companyRows.filter((c) => (c.n_filings || 0) >= 3).length;
  const analyzed = companyRows.reduce((n, c) => n + (c.n_filings || 0), 0);
  const empty = companyRows.length === 0;

  return (
    <>
      <section className="hero">
        <div className="kicker">S&amp;P 500 · MD&amp;A vs the statements</div>
        <h1>Does the tone match the numbers?</h1>
        <p className="lede">
          We score Management&apos;s Discussion &amp; Analysis with FinBERT and compare it to
          same-filing YoY revenue and net income. The headline view is{" "}
          <strong>by industry</strong> — company samples are small.
        </p>
      </section>

      <div className="panel">
        <div className="kicker">Cache</div>
        <p style={{ margin: "8px 0 12px" }}>
          {status?.running
            ? status.message || "Worker running…"
            : status?.stage === "done"
              ? status.message || "Aggregates are up to date."
              : status?.message ||
                (empty
                  ? "Waiting for the local worker to publish sector and company aggregates."
                  : "Published aggregates loaded from Supabase.")}
        </p>
        <div className="progress">
          <div
            className="progress-bar"
            style={{
              width: `${Math.min(100, ready && companyRows.length ? Math.round((ready / Math.max(companyRows.length, 1)) * 100) : 0)}%`,
            }}
          />
        </div>
        <p className="note">
          {ready} companies with ≥3 filings · {analyzed} filings in rollup
          {coverage?.analyzed != null ? ` · local analyzed ${coverage.analyzed}` : ""}
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
          <div className="label">Filings rolled up</div>
          <div className="value">{analyzed || "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Ready (≥3)</div>
          <div className="value">{ready || "—"}</div>
        </div>
      </div>

      <div className="rank-grid">
        <SectorRankTable
          title="Most correlated industries"
          rows={mostSectors}
          empty="No sector correlations yet — run the worker and push_all."
        />
        <SectorRankTable
          title="Least correlated industries"
          rows={leastSectors}
          empty="No sector correlations yet."
        />
      </div>

      <div className="rank-grid">
        <CompanyRankTable
          title="Most correlated companies"
          rows={mostCompanies}
          empty="No company correlations yet."
        />
        <CompanyRankTable
          title="Least correlated companies"
          rows={leastCompanies}
          empty="No company correlations yet."
        />
      </div>

      <CompanyBrowser companies={companyRows} />
    </>
  );
}
