import Link from "next/link";
import MethodologyLink from "@/components/MethodologyLink";
import { loadSiteData } from "@/lib/data";
import { relationshipFromRho } from "@/lib/explain";
import { fmtCount } from "@/lib/format";
import { isDefaultEligible } from "@/lib/phase5";
import { sectorSlug } from "@/lib/sector";

export const revalidate = 3600;

export default async function IndustriesIndexPage() {
  const { sectors, companies } = await loadSiteData();
  const rows = [...sectors].sort((a, b) => a.sector.localeCompare(b.sector));

  return (
    <>
      <section className="hero">
        <div className="kicker">S&amp;P 500 industries</div>
        <h1>Industries</h1>
        <p className="lede">
          Each industry shows what a typical filing looks like and what a typical company looks
          like.{" "}
          <MethodologyLink topic="sector-weighting">Why are these different?</MethodologyLink>
        </p>
      </section>

      <div className="industry-card-grid">
        {rows.map((row) => {
          const rho =
            row.fw_spearman_rho_10q_ni ??
            row.primary_10q_ni?.filing_weighted_spearman_rho ??
            null;
          const cb =
            row.cb_pearson_r_10q_ni ?? row.primary_10q_ni?.company_balanced_pearson_r ?? null;
          const eligible = companies.filter(
            (c) => c.sector === row.sector && isDefaultEligible(c)
          ).length;
          const fw = relationshipFromRho(rho);
          const cbl = relationshipFromRho(cb);
          return (
            <Link
              key={row.sector}
              href={`/industries/${sectorSlug(row.sector)}`}
              className="industry-card"
            >
              <h2>{row.sector}</h2>
              <p className="muted tiny">
                {fmtCount(row.n_companies)} companies · {fmtCount(row.n_filings)} filings ·{" "}
                {fmtCount(eligible)} on main board
              </p>
              <div className="snap-row">
                <span className="muted tiny">Typical filing</span>
                <span className={`rel-label ${fw.tone}`}>{fw.short}</span>
              </div>
              <div className="snap-row">
                <span className="muted tiny">Typical company</span>
                <span className={`rel-label ${cbl.tone}`}>{cbl.short}</span>
              </div>
              <p className="industry-interp muted tiny">
                {fw.band === "little" && cbl.band === "little"
                  ? "Both views look relatively flat."
                  : fw.tone === cbl.tone
                    ? "Filing-level and company-level views point in a similar direction."
                    : "Filing-level and company-level views can diverge. Weighting matters."}
              </p>
            </Link>
          );
        })}
      </div>
    </>
  );
}
