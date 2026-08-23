import Link from "next/link";
import { notFound } from "next/navigation";
import SentimentScatter from "@/components/SentimentScatter";
import { fmtAgreePct, fmtCI, fmtPct, fmtQ, fmtR, fmtScore, toneClass } from "@/lib/format";
import { loadCompany } from "@/lib/data";
import { formIs10K, formIs10Q, isFdrSignificant, isLimitedSample, ni10q } from "@/lib/phase5";
import { sectorSlug } from "@/lib/sector";

export const revalidate = 3600;

export default async function CompanyPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker: raw } = await params;
  const ticker = raw.toUpperCase();
  const { company, examples: exampleRows } = await loadCompany(ticker);
  if (!company) notFound();
  const row = company;
  const ni = ni10q(row);
  const rev = row.secondary_10q_revenue;
  const niK = row.secondary_10k_ni;

  const scatter = (row.points ?? [])
    .filter((p) => formIs10Q(p.form) && p.sentiment != null && p.income_pct != null)
    .map((p) => ({
      form: p.form,
      filed: p.filed,
      sentiment: Number((p.sentiment as number).toFixed(4)),
      income: Number(((p.income_pct as number) * 100).toFixed(2)),
    }));

  const points10q = (row.points ?? []).filter((p) => formIs10Q(p.form));
  const points10k = (row.points ?? []).filter((p) => formIs10K(p.form));

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
          {isFdrSignificant(row) ? (
            <span className="badge-fdr" title="FDR q < 0.05 among ranking-eligible companies">
              FDR-adjusted significance
            </span>
          ) : null}
        </h1>
        <p className="lede">
          Primary analysis: <strong>10-Q MD&amp;A tone vs Net Income YoY</strong> (same filing).
          {isLimitedSample(row)
            ? " Limited sample (n=6–7) — shown on the company page, excluded from the default board."
            : ni.n < 6
              ? " Insufficient n for public ranking."
              : " Eligible for the default n≥8 board."}{" "}
          Contemporaneous association only — not predictive.
        </p>
      </section>

      <div className="stats">
        <div className="stat" title="Spearman rank association (emphasized)">
          <div className="label">Spearman ρ (10-Q NI)</div>
          <div className={`value ${toneClass(ni.spearman_rho)}`}>{fmtR(ni.spearman_rho)}</div>
        </div>
        <div className="stat" title="Pearson linear association with Fisher 95% CI">
          <div className="label">Pearson r (10-Q NI)</div>
          <div className={`value ${toneClass(ni.pearson_r)}`}>{fmtR(ni.pearson_r)}</div>
        </div>
        <div className="stat">
          <div className="label">n / agreement</div>
          <div className="value">
            {ni.n || "—"}
            <span className="muted" style={{ fontSize: "0.45em", display: "block" }}>
              {ni.agree_label ?? (ni.agree_pct != null ? fmtAgreePct(ni.agree_pct) : "—")}
            </span>
          </div>
        </div>
        <div className="stat" title="Benjamini–Hochberg q among ranking-eligible companies">
          <div className="label">FDR q</div>
          <div className="value">{fmtQ(ni.fdr_q)}</div>
        </div>
      </div>

      <div className="panel">
        <h2>10-Q net income detail</h2>
        <p className="hint">
          Spearman is shown first for robustness to extreme YoY base effects. Pearson includes a
          95% Fisher CI. FDR q is not proof or certainty.
        </p>
        <table>
          <tbody>
            <tr>
              <th>Spearman ρ</th>
              <td className={toneClass(ni.spearman_rho)}>
                {fmtR(ni.spearman_rho)} <span className="muted">(p={fmtQ(ni.spearman_p)})</span>
              </td>
            </tr>
            <tr>
              <th>Pearson r</th>
              <td className={toneClass(ni.pearson_r)}>
                {fmtR(ni.pearson_r)} <span className="muted">(p={fmtQ(ni.pearson_p)})</span>
              </td>
            </tr>
            <tr>
              <th>95% CI (Pearson)</th>
              <td>{fmtCI(ni.ci_low, ni.ci_high)}</td>
            </tr>
            <tr>
              <th>Agreement</th>
              <td>
                {ni.agree_label ?? "—"}
                {ni.agree_num != null && ni.agree_den != null
                  ? ` (${ni.agree_num} / ${ni.agree_den})`
                  : ""}
              </td>
            </tr>
            <tr>
              <th>Reliability</th>
              <td>{ni.reliability?.replace(/_/g, " ") ?? "—"}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Sentiment vs net income change (10-Q)</h2>
        <p className="hint">
          Each point is one 10-Q. X is MD&amp;A tone; Y is YoY net income (%). Primary n = {ni.n || "—"}.
        </p>
        <SentimentScatter points={scatter} />
      </div>

      <div className="panel">
        <h2>Revenue (secondary)</h2>
        {!rev?.available ? (
          <p className="hint">
            {rev?.reason === "sector_not_comparable_revenue" ||
            row.sector === "Financials" ||
            row.sector === "Real Estate"
              ? "Revenue comparison not used due to cross-company concept comparability."
              : "No valid 10-Q revenue pairs for this company."}
          </p>
        ) : (
          <>
            <p className="hint">Secondary to net income. Same-filing 10-Q association.</p>
            <div className="stats">
              <div className="stat">
                <div className="label">Spearman ρ</div>
                <div className={`value ${toneClass(rev.stats?.spearman_rho ?? null)}`}>
                  {fmtR(rev.stats?.spearman_rho)}
                </div>
              </div>
              <div className="stat">
                <div className="label">Pearson r</div>
                <div className={`value ${toneClass(rev.stats?.pearson_r ?? null)}`}>
                  {fmtR(rev.stats?.pearson_r)}
                </div>
              </div>
              <div className="stat">
                <div className="label">n</div>
                <div className="value">{rev.stats?.n ?? "—"}</div>
              </div>
              <div className="stat">
                <div className="label">FDR q</div>
                <div className="value">{fmtQ(rev.stats?.fdr_q)}</div>
              </div>
            </div>
          </>
        )}
      </div>

      <details className="panel">
        <summary>
          <strong>10-K analysis (secondary)</strong>
          <span className="muted"> — collapsed; not mixed into primary rankings</span>
        </summary>
        <p className="hint" style={{ marginTop: 12 }}>
          Annual samples are shorter. Shown for context only.
        </p>
        <div className="stats">
          <div className="stat">
            <div className="label">Spearman ρ</div>
            <div className={`value ${toneClass(niK?.spearman_rho ?? null)}`}>
              {fmtR(niK?.spearman_rho)}
            </div>
          </div>
          <div className="stat">
            <div className="label">Pearson r</div>
            <div className={`value ${toneClass(niK?.pearson_r ?? null)}`}>
              {fmtR(niK?.pearson_r)}
            </div>
          </div>
          <div className="stat">
            <div className="label">n</div>
            <div className="value">{niK?.n ?? "—"}</div>
          </div>
          <div className="stat">
            <div className="label">Agreement</div>
            <div className="value">{niK?.agreement_label ?? "—"}</div>
          </div>
        </div>
      </details>

      <div className="panel">
        <h2>Filing points</h2>
        <p className="hint">
          Compact metrics only. 10-Q rows feed the primary chart; 10-K listed separately below.
        </p>
        <h3 className="subhead">10-Q</h3>
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
            {points10q.map((p, i) => (
              <tr key={`${p.accession || p.filed}-${i}`}>
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
        {points10k.length ? (
          <>
            <h3 className="subhead">10-K (secondary)</h3>
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
                {points10k.map((p, i) => (
                  <tr key={`${p.accession || p.filed}-k-${i}`}>
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
          </>
        ) : null}
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
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}
