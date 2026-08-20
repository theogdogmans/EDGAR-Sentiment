import Link from "next/link";
import { notFound } from "next/navigation";
import SentimentScatter from "@/components/SentimentScatter";
import { fmtPct, fmtR, fmtScore, toneClass } from "@/lib/format";
import { findSectorBySlug, sectorSlug } from "@/lib/sector";
import { createSupabaseClient } from "@/lib/supabase";
import type { CompanyStat, SectorStat } from "@/lib/types";

export const revalidate = 3600;

export default async function IndustryPage({
  params,
}: {
  params: Promise<{ sector: string }>;
}) {
  const { sector: slug } = await params;
  const supabase = createSupabaseClient();
  const [{ data: sectors }, { data: companies }] = await Promise.all([
    supabase.from("sector_stats").select("*"),
    supabase.from("company_stats").select("*").order("ticker"),
  ]);

  const sectorList = (sectors ?? []) as SectorStat[];
  const match = findSectorBySlug(sectorList, slug);
  if (!match) notFound();

  const members = ((companies ?? []) as CompanyStat[])
    .filter((c) => c.sector === match.sector)
    .sort((a, b) => {
      const ar = a.r_income;
      const br = b.r_income;
      if (ar == null && br == null) return a.ticker.localeCompare(b.ticker);
      if (ar == null) return 1;
      if (br == null) return -1;
      return br - ar;
    });

  const scatter = (match.points ?? [])
    .filter((p) => p.sentiment != null && p.income_pct != null)
    .map((p) => ({
      ticker: p.ticker,
      form: p.form,
      filed: p.filed,
      sentiment: Number((p.sentiment as number).toFixed(4)),
      income: Number(((p.income_pct as number) * 100).toFixed(2)),
    }));

  return (
    <>
      <p className="back">
        <Link href="/">← Rankings</Link>
      </p>
      <section className="hero">
        <div className="kicker">Industry</div>
        <h1>{match.sector}</h1>
        <p className="lede">
          Pooled MD&amp;A sentiment vs YoY net income across {match.n_companies} S&amp;P 500
          companies in this sector ({match.n_filings} scored filings in the rollup).
        </p>
      </section>

      <div className="stats">
        <div className="stat">
          <div className="label">r vs net income</div>
          <div className={`value ${toneClass(match.r_income)}`}>{fmtR(match.r_income)}</div>
        </div>
        <div className="stat">
          <div className="label">r vs revenue</div>
          <div className={`value ${toneClass(match.r_revenue)}`}>{fmtR(match.r_revenue)}</div>
        </div>
        <div className="stat">
          <div className="label">Income agreement</div>
          <div className="value">{fmtPct(match.agreement_income)}</div>
        </div>
        <div className="stat">
          <div className="label">Mean sentiment</div>
          <div className={`value ${toneClass(match.mean_sentiment)}`}>
            {fmtScore(match.mean_sentiment)}
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Pooled scatter</h2>
        <p className="hint">
          Each point is one filing. n for income correlation: {match.n_income || "—"}.
        </p>
        <SentimentScatter points={scatter} />
      </div>

      <div className="panel">
        <h2>Companies in {match.sector}</h2>
        <p className="hint">Sorted by company-level r (small samples — illustrative only).</p>
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th>r (income)</th>
              <th>n</th>
              <th>Agree</th>
              <th>Mean tone</th>
            </tr>
          </thead>
          <tbody>
            {members.map((c) => (
              <tr key={c.ticker} className="row-link">
                <td>
                  <Link href={`/company/${c.ticker}`}>{c.display || c.ticker}</Link>
                </td>
                <td>{c.name}</td>
                <td className={toneClass(c.r_income)}>{fmtR(c.r_income)}</td>
                <td>{c.n_income || "—"}</td>
                <td>{fmtPct(c.agreement_income)}</td>
                <td className={toneClass(c.mean_sentiment)}>{fmtScore(c.mean_sentiment)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="note">
        Other industries:{" "}
        {sectorList
          .filter((s) => s.sector !== match.sector)
          .slice(0, 8)
          .map((s, i) => (
            <span key={s.sector}>
              {i ? " · " : ""}
              <Link href={`/industries/${sectorSlug(s.sector)}`}>{s.sector}</Link>
            </span>
          ))}
      </p>
    </>
  );
}
