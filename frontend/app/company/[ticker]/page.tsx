import Link from "next/link";
import { notFound } from "next/navigation";
import SentimentScatter from "@/components/SentimentScatter";
import { fmtPct, fmtR, fmtScore, toneClass } from "@/lib/format";
import { sectorSlug } from "@/lib/sector";
import { createSupabaseClient } from "@/lib/supabase";
import type { CompanyStat, ExampleFiling } from "@/lib/types";

export const revalidate = 3600;

export default async function CompanyPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker: raw } = await params;
  const ticker = raw.toUpperCase();
  const supabase = createSupabaseClient();
  const { data: company } = await supabase
    .from("company_stats")
    .select("*")
    .eq("ticker", ticker)
    .maybeSingle();
  if (!company) notFound();
  const row = company as CompanyStat;

  const { data: examples } = await supabase
    .from("example_filings")
    .select("*")
    .eq("ticker", ticker)
    .order("filed", { ascending: false });
  const exampleRows = (examples ?? []) as ExampleFiling[];

  const scatter = (row.points ?? [])
    .filter((p) => p.sentiment != null && p.income_pct != null)
    .map((p) => ({
      form: p.form,
      filed: p.filed,
      sentiment: Number((p.sentiment as number).toFixed(4)),
      income: Number(((p.income_pct as number) * 100).toFixed(2)),
    }));

  return (
    <>
      <p className="back">
        <Link href="/">← Rankings</Link>
        {row.sector ? (
          <>
            {" · "}
            <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
          </>
        ) : null}
      </p>

      <section className="hero">
        <div className="kicker">{row.cik ? `CIK ${row.cik}` : "S&P 500"}</div>
        <h1>
          {row.display || row.ticker}{" "}
          <span className="muted" style={{ fontSize: "0.55em" }}>
            {row.name}
          </span>
        </h1>
        <p className="lede">
          Company-level correlation uses only {row.n_filings || 0} scored filings. Prefer the{" "}
          {row.sector ? (
            <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
          ) : (
            "industry"
          )}{" "}
          view for a stabler sample.
        </p>
      </section>

      <div className="stats">
        <div className="stat">
          <div className="label">r vs net income</div>
          <div className={`value ${toneClass(row.r_income)}`}>{fmtR(row.r_income)}</div>
        </div>
        <div className="stat">
          <div className="label">r vs revenue</div>
          <div className={`value ${toneClass(row.r_revenue)}`}>{fmtR(row.r_revenue)}</div>
        </div>
        <div className="stat">
          <div className="label">Income agreement</div>
          <div className="value">{fmtPct(row.agreement_income)}</div>
        </div>
        <div className="stat">
          <div className="label">Mean sentiment</div>
          <div className={`value ${toneClass(row.mean_sentiment)}`}>
            {fmtScore(row.mean_sentiment)}
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Sentiment vs net income change</h2>
        <p className="hint">
          Each point is one 10-K or 10-Q. X is MD&amp;A tone; Y is YoY net income. n ={" "}
          {row.n_income || "—"}.
        </p>
        <SentimentScatter points={scatter} />
      </div>

      <div className="panel">
        <h2>Filing points in the rollup</h2>
        <p className="hint">Compact metrics only — sentence highlights appear for featured examples.</p>
        <table>
          <thead>
            <tr>
              <th>Filing</th>
              <th>Sentiment</th>
              <th>Revenue YoY</th>
              <th>Net income YoY</th>
            </tr>
          </thead>
          <tbody>
            {(row.points ?? []).map((p, i) => (
              <tr key={`${p.filed}-${i}`}>
                <td>
                  {p.form} {p.filed}
                </td>
                <td className={toneClass(p.sentiment)}>{fmtScore(p.sentiment)}</td>
                <td className={toneClass(p.revenue_pct)}>{fmtPct(p.revenue_pct)}</td>
                <td className={toneClass(p.income_pct)}>{fmtPct(p.income_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {exampleRows.length ? (
        <div className="panel">
          <h2>Featured filing detail</h2>
          <p className="hint">Sentence-level FinBERT highlights for case studies only.</p>
          <ul className="prose-list">
            {exampleRows.map((f) => (
              <li key={f.accession}>
                <Link href={`/company/${ticker}/filing/${f.accession}`}>
                  {f.form} filed {f.filed}
                </Link>
                {f.role ? ` · ${f.role.replace(/_/g, " ")}` : ""}
                {f.risk_sentiment_score != null
                  ? ` · MD&A ${fmtScore(f.sentiment_score)} vs Item 1A ${fmtScore(f.risk_sentiment_score)}`
                  : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}
