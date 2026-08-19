import Link from "next/link";
import { notFound } from "next/navigation";
import SentimentScatter from "@/components/SentimentScatter";
import { fmtPct, fmtR, fmtScore, toneClass } from "@/lib/format";
import { pearson } from "@/lib/stats";
import { createSupabaseClient } from "@/lib/supabase";

export const revalidate = 30;

type FilingRow = {
  accession: string;
  ticker: string;
  form: string;
  filed: string;
  report_date: string | null;
  filing_url: string | null;
  sentiment_score: number | null;
  metrics: {
    revenue?: { pct_change?: number | null } | null;
    net_income?: { pct_change?: number | null } | null;
  } | null;
  agreement: { net_income?: boolean | null; revenue?: boolean | null } | null;
};

export default async function CompanyPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker: raw } = await params;
  const ticker = raw.toUpperCase();
  const supabase = createSupabaseClient();
  const { data: company } = await supabase.from("companies").select("*").eq("ticker", ticker).maybeSingle();
  if (!company) notFound();

  const { data: filings } = await supabase
    .from("filings")
    .select("accession, ticker, form, filed, report_date, filing_url, sentiment_score, metrics, agreement")
    .eq("ticker", ticker)
    .order("filed", { ascending: false });

  const rows = (filings ?? []) as FilingRow[];
  const scored = rows.filter((f) => f.sentiment_score != null && f.metrics?.net_income?.pct_change != null);
  const revPairs = rows.filter((f) => f.sentiment_score != null && f.metrics?.revenue?.pct_change != null);
  const incomeAgree = rows.map((f) => f.agreement?.net_income).filter((v): v is boolean => v === true || v === false);
  const rIncome = pearson(
    scored.map((f) => f.sentiment_score as number),
    scored.map((f) => f.metrics!.net_income!.pct_change as number)
  );
  const rRevenue = pearson(
    revPairs.map((f) => f.sentiment_score as number),
    revPairs.map((f) => f.metrics!.revenue!.pct_change as number)
  );
  const scatter = scored.map((f) => ({
    accession: f.accession,
    form: f.form,
    filed: f.filed,
    sentiment: Number((f.sentiment_score as number).toFixed(4)),
    income: Number(((f.metrics!.net_income!.pct_change as number) * 100).toFixed(2)),
  }));
  const analyzed = rows.filter((f) => f.sentiment_score != null).length;

  return (
    <main>
      <p className="back">
        <Link href="/">← S&P 500</Link>
      </p>
      <div className="kicker">{company.cik ? `CIK ${company.cik}` : "S&P 500"}</div>
      <h1>{company.name}</h1>
      <p className="lede">
        Sentiment is FinBERT on MD&A sentences. Numbers are year-over-year changes for the same
        filing period. This page reads from Supabase, not live EDGAR.
      </p>
      <p className="note">
        {analyzed}/{rows.length} filings scored
        {analyzed < rows.length ? " · remaining scores sync as the local worker finishes." : " · loaded from cache."}
      </p>
      <section className="stats">
        <div className="stat">
          <div className="label">r vs net income</div>
          <div className="value">{fmtR(rIncome.r)}</div>
        </div>
        <div className="stat">
          <div className="label">r vs revenue</div>
          <div className="value">{fmtR(rRevenue.r)}</div>
        </div>
        <div className="stat">
          <div className="label">Income agreement</div>
          <div className="value">
            {fmtPct(incomeAgree.length ? incomeAgree.filter(Boolean).length / incomeAgree.length : null)}
          </div>
        </div>
        <div className="stat">
          <div className="label">Analyzed</div>
          <div className="value">
            {analyzed}/{rows.length || "—"}
          </div>
        </div>
      </section>
      <section className="panel">
        <h2>Sentiment vs net income change</h2>
        <p className="hint">Each point is one 10-K or 10-Q. X is MD&A tone; Y is YoY net income.</p>
        <SentimentScatter points={scatter} />
      </section>
      <section className="panel">
        <h2>Recent filings</h2>
        <p className="hint">Agreement means tone and the metric moved in the same direction.</p>
        <table>
          <thead>
            <tr>
              <th>Filing</th>
              <th>Sentiment</th>
              <th>Revenue YoY</th>
              <th>Net income YoY</th>
              <th>Agree?</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.accession} className="row-link">
                <td>
                  <Link href={`/company/${ticker}/filing/${f.accession}`}>
                    <span className="badge">{f.form}</span> {f.filed}
                  </Link>
                  <div className="muted">{f.report_date || f.accession}</div>
                </td>
                <td className={toneClass(f.sentiment_score)}>
                  {f.sentiment_score == null ? "…" : fmtScore(f.sentiment_score)}
                </td>
                <td className={toneClass(f.metrics?.revenue?.pct_change)}>
                  {fmtPct(f.metrics?.revenue?.pct_change)}
                </td>
                <td className={toneClass(f.metrics?.net_income?.pct_change)}>
                  {fmtPct(f.metrics?.net_income?.pct_change)}
                </td>
                <td>
                  {f.agreement?.net_income == null ? "—" : f.agreement.net_income ? "Yes" : "No"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
