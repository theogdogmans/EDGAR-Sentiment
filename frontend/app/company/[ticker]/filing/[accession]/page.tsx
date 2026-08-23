import Link from "next/link";
import { notFound } from "next/navigation";
import { loadExampleFiling } from "@/lib/data";
import { fmtMoney, fmtPct, fmtScore, toneClass } from "@/lib/format";
import type { ExampleFiling } from "@/lib/types";

export const revalidate = 3600;

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
  const filing = await loadExampleFiling(ticker, accession);
  if (!filing || filing.ticker !== ticker) notFound();
  const row = filing as ExampleFiling;

  const sentences = row.sentences ?? [];
  const riskSentences = row.risk_sentences ?? [];
  const metrics = [
    ["Revenue", row.metrics?.revenue as Metric],
    ["Net income", row.metrics?.net_income as Metric],
    ["Operating income", row.metrics?.operating_income as Metric],
    ["Diluted EPS", row.metrics?.eps as Metric],
  ] as const;

  return (
    <>
      <p className="back">
        <Link href={`/company/${ticker}`}>← {ticker}</Link>
      </p>
      <section className="hero">
        <div className="kicker">
          {row.form} · {accession}
          {row.role ? ` · ${row.role.replace(/_/g, " ")}` : ""}
        </div>
        <h1>
          {row.form} filed {row.filed}
        </h1>
        <p className="lede">
          Featured example filing. Sentence highlights are stored only for a small case-study set.
        </p>
      </section>

      <div className="stats">
        <div className="stat">
          <div className="label">MD&amp;A sentiment</div>
          <div className={`value ${toneClass(row.sentiment_score)}`}>
            {fmtScore(row.sentiment_score)}
          </div>
        </div>
        <div className="stat">
          <div className="label">Positive / negative</div>
          <div className="value" style={{ fontSize: 22 }}>
            {fmtPct(row.positive_share)} / {fmtPct(row.negative_share)}
          </div>
        </div>
        <div className="stat">
          <div className="label">Sentences scored</div>
          <div className="value">{row.sentence_count ?? "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Income agreement</div>
          <div className="value">
            {row.agreement?.net_income == null
              ? "—"
              : row.agreement.net_income
                ? "Yes"
                : "No"}
          </div>
        </div>
      </div>

      {row.risk_sentiment_score != null ? (
        <div className="panel">
          <h2>Section bias: MD&amp;A vs Item 1A</h2>
          <p className="hint">
            Risk Factors are legally conservative. Expect a more negative FinBERT score than MD&amp;A
            on the same 10-K.
          </p>
          <div className="stats">
            <div className="stat">
              <div className="label">MD&amp;A</div>
              <div className={`value ${toneClass(row.sentiment_score)}`}>
                {fmtScore(row.sentiment_score)}
              </div>
            </div>
            <div className="stat">
              <div className="label">Item 1A Risk Factors</div>
              <div className={`value ${toneClass(row.risk_sentiment_score)}`}>
                {fmtScore(row.risk_sentiment_score)}
              </div>
            </div>
            <div className="stat">
              <div className="label">Gap (MD&amp;A − 1A)</div>
              <div
                className={`value ${toneClass(
                  row.sentiment_score != null
                    ? row.sentiment_score - row.risk_sentiment_score
                    : null
                )}`}
              >
                {fmtScore(
                  row.sentiment_score != null
                    ? row.sentiment_score - row.risk_sentiment_score
                    : null
                )}
              </div>
            </div>
            <div className="stat">
              <div className="label">1A sentences</div>
              <div className="value">{row.risk_sentence_count ?? "—"}</div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="metrics-grid">
        {metrics.map(([label, metric]) => (
          <div className="metric-card" key={label}>
            <div className="label">{label}</div>
            <div className="value" style={{ fontSize: 22, marginTop: 4 }}>
              {fmtMoney(metric?.value, metric?.unit)}
            </div>
            <div className={`muted ${toneClass(metric?.pct_change)}`}>
              {fmtPct(metric?.pct_change)} vs prior {metric?.fp || "period"}
            </div>
          </div>
        ))}
      </div>

      {row.filing_url ? (
        <p className="note">
          <a href={row.filing_url} target="_blank" rel="noreferrer">
            Open original filing on EDGAR
          </a>
        </p>
      ) : null}

      <div className="panel">
        <h2>MD&amp;A sentences</h2>
        <p className="hint">Green is FinBERT-positive, red is negative.</p>
        {!sentences.length ? (
          <p className="muted">No sentence highlights for this example.</p>
        ) : (
          sentences.map((s, i) => (
            <div className={`sentence ${s.label}`} key={i}>
              <div className="meta">
                {s.label} · {fmtScore(s.score)}
              </div>
              {s.text}
            </div>
          ))
        )}
      </div>

      {riskSentences.length ? (
        <div className="panel">
          <h2>Item 1A sentences</h2>
          <p className="hint">Same model, different section — usually more negative.</p>
          {riskSentences.map((s, i) => (
            <div className={`sentence ${s.label}`} key={i}>
              <div className="meta">
                {s.label} · {fmtScore(s.score)}
              </div>
              {s.text}
            </div>
          ))}
        </div>
      ) : null}
    </>
  );
}
