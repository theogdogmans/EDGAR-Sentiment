import Link from "next/link";
import MethodologyLink from "@/components/MethodologyLink";
import { loadSiteData } from "@/lib/data";
import { relationshipFromRho } from "@/lib/explain";
import { fmtR, toneClass } from "@/lib/format";
import { sectorSlug } from "@/lib/sector";

export const revalidate = 3600;

export default async function IndustriesIndexPage() {
  const { sectors } = await loadSiteData();
  const rows = [...sectors].sort((a, b) => a.sector.localeCompare(b.sector));

  return (
    <>
      <section className="hero">
        <div className="kicker">S&amp;P 500 industries</div>
        <h1>Industries</h1>
        <p className="lede">
          Each industry page shows two views: what a typical filing looks like, and what a typical
          company looks like.{" "}
          <MethodologyLink topic="sector-weighting">Why are these different? →</MethodologyLink>
        </p>
      </section>

      <div className="panel">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Industry</th>
                <th>Typical filing</th>
                <th>Typical company</th>
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
                return (
                  <tr key={row.sector} className="row-link">
                    <td>
                      <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
                    </td>
                    <td>
                      <div className={toneClass(rho)}>{relationshipFromRho(rho).short}</div>
                      <div className="muted tiny">Spearman {fmtR(rho)}</div>
                    </td>
                    <td>
                      <div className={toneClass(cb)}>{relationshipFromRho(cb).short}</div>
                      <div className="muted tiny">Pearson {fmtR(cb)}</div>
                    </td>
                    <td>{row.n_companies}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
