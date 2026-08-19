import Link from "next/link";
import { notFound } from "next/navigation";
import { fmtMoney, fmtPct, fmtScore, toneClass } from "@/lib/format";
import { createSupabaseClient } from "@/lib/supabase";

export const revalidate = 30;

type Metric = {
  value?: number;
  unit?: string;
  pct_change?: number | null;
  fp?: string;
} | null;

export default async function FilingPage({
  params,
}: {
  params: Promise<{ ticker: string; accession: string }>;
}) {
  const { ticker: rawTicker, accession } = await params;
  const ticker = rawTicker.toUpperCase();
  const supabase = createSupabaseClient();
  const { data: filing } = await supabase.from("filings").select("*").eq("accession", accession).maybeSingle();
  if (!filing) notFound();

  const sentences = (filing.sentences as { text: string; label: string; score: number }[] | null) ?? [];
  const metrics = [
    ["Revenue", filing.metrics?.revenue as Metric],
    ["Net income", filing.metrics?.net_income as Metric],
    ["Operating income", filing.metrics?.operating_income as Metric],
    ["Diluted EPS", filing.metrics?.eps as Metric],
  ] as const;

  return (
    <main>
      <p className="back">
        <Link href={`/company/${ticker}`}>← {ticker}</Link>
      </p>
      <div className="kicker">{filing.form} · {accession}</div>
      <h1>
        {filing.form} filed {filing.filed}
      </h1>
      <section className="stats">
        <div className="stat">
          <div className="label">MD&A sentiment</div>
          <div className={`value ${toneClass(filing.sentiment_score)}`}>{fmtScore(filing.sentiment_score)}</div>
        </div>
        <div className="stat">
          <div className="label">Positive / negative</div>
          <div className="value">
            {fmtPct(filing.positive_share)} / {fmtPct(filing.negative_share)}
          </div>
        </div>
        <div className="stat">
          <div className="label">Sentences scored</div>
          <div className="value">{filing.sentence_count ?? "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Income agreement</div>
          <div className="value">
            {filing.agreement?.net_income == null ? "—" : filing.agreement.net_income ? "Yes" : "No"}
          </div>
        </div>
      </section>
      <section className="metrics-grid">
        {metrics.map(([label, metric]) => (
          <div className="metric-card" key={label}>
            <div className="kicker">{label}</div>
            <div className="value" style={{ fontSize: 24, fontFamily: "var(--font-serif), Georgia, serif" }}>
              {fmtMoney(metric?.value, metric?.unit)}
            </div>
            <div className={toneClass(metric?.pct_change)}>
              {fmtPct(metric?.pct_change)} vs prior {metric?.fp || "period"}
            </div>
          </div>
        ))}
      </section>
      <p className="note">
        {filing.filing_url ? (
          <a href={filing.filing_url} target="_blank" rel="noreferrer">
            Open original filing on EDGAR
          </a>
        ) : null}
      </p>
      <section className="panel">
        <h2>MD&A sentences</h2>
        <p className="hint">Green is FinBERT-positive, red is negative. Neutral stays on the paper rule.</p>
        {sentences.length === 0 ? (
          <p className="muted">Sentence-level scores have not synced for this filing yet.</p>
        ) : (
          sentences.map((s, i) => (
            <div className={`sentence ${s.label}`} key={`${i}-${s.text.slice(0, 24)}`}>
              <div className="meta">
                {s.label} · {fmtScore(s.score)}
              </div>
              {s.text}
            </div>
          ))
        )}
      </section>
    </main>
  );
}
