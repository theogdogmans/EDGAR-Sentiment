import Link from "next/link";
import { notFound } from "next/navigation";
import FdrBadge from "@/components/FdrBadge";
import MethodologyLink from "@/components/MethodologyLink";
import SentimentScatter from "@/components/SentimentScatter";
import TermTip from "@/components/TermTip";
import {
  agreementSentence,
  companyTakeaway,
  observationsPhrase,
  relationshipFromRho,
  sampleSizeLabel,
} from "@/lib/explain";
import { fmtCI, fmtPct, fmtQ, fmtR, fmtRExact, fmtScore, toneClass } from "@/lib/format";
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
  const label = relationshipFromRho(ni.spearman_rho);
  const fdr = isFdrSignificant(row);
  const takeaway = companyTakeaway(row.name || row.display || row.ticker, ni.spearman_rho, fdr);
  const agreeText = agreementSentence(ni.agree_num, ni.agree_den);

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
        <Link href="/#companies">← Companies</Link>
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
        <p className="lede takeaway">{takeaway}</p>
        <p className="note">
          Contemporaneous association only — not predictive.{" "}
          <Link href="/methodology#limitations">Limitations →</Link>
        </p>
      </section>

      <section className="panel result-card" aria-labelledby="main-result">
        <h2 id="main-result">Main result</h2>
        <p className="hint">
          Primary comparison: quarterly <TermTip term="mda">MD&amp;A</TermTip> tone vs net income{" "}
          <TermTip term="yoy">YoY</TermTip>.
        </p>
        <div className="result-grid">
          <div>
            <div className="label">Relationship</div>
            <div className={`rel-label lg ${label.tone}`}>{label.short}</div>
            <MethodologyLink topic="relationship-labels">View explanation →</MethodologyLink>
          </div>
          <div>
            <div className="label">
              Primary measure (<TermTip term="spearman">Spearman</TermTip>)
            </div>
            <div className={`value ${toneClass(ni.spearman_rho)}`}>{fmtR(ni.spearman_rho)}</div>
            <MethodologyLink topic="spearman">What does this mean? →</MethodologyLink>
          </div>
          <div>
            <div className="label">Sample</div>
            <div className="value-sm">{observationsPhrase(ni.n)}</div>
            <div className="muted tiny">{sampleSizeLabel(ni.n)}</div>
            <MethodologyLink topic="sample-size">Why sample size matters →</MethodologyLink>
          </div>
          <div>
            <div className="label">Multiple-testing check</div>
            {fdr ? (
              <FdrBadge active />
            ) : (
              <p className="muted tiny">
                Does not remain notable after adjusting for hundreds of company tests.{" "}
                <MethodologyLink topic="fdr">Why that matters →</MethodologyLink>
              </p>
            )}
          </div>
        </div>
        <div className="secondary-stat">
          <span>
            Secondary (<TermTip term="pearson">Pearson</TermTip>): {fmtR(ni.pearson_r)}
          </span>
          <MethodologyLink topic="correlation">Why show both? →</MethodologyLink>
        </div>
        {isLimitedSample(row) ? (
          <p className="note">
            Limited sample (6–7 quarters) — shown here, excluded from the default public board.
          </p>
        ) : ni.n < 6 ? (
          <p className="note">Insufficient sample for public ranking.</p>
        ) : null}
      </section>

      <div className="panel">
        <h2>Tone vs earnings change</h2>
        <p className="hint">
          Each dot represents one 10-Q filing. Left–right is MD&amp;A tone; up–down is year-over-year
          net income change.{" "}
          <MethodologyLink topic="scatterplots">How to read this chart →</MethodologyLink>
        </p>
        <SentimentScatter points={scatter} />
      </div>

      {agreeText ? (
        <div className="panel">
          <h2>Direction agreement</h2>
          <p className="lede-sm">{agreeText}</p>
          <p className="muted">
            {ni.agree_num} / {ni.agree_den} direction agreement
          </p>
          <MethodologyLink topic="agreement">How is agreement calculated? →</MethodologyLink>
        </div>
      ) : null}

      <details className="panel">
        <summary>
          <strong>Statistical details</strong>
          <span className="muted"> — Pearson, p-values, q, confidence interval</span>
        </summary>
        <table style={{ marginTop: 12 }}>
          <tbody>
            <tr>
              <th>Spearman ρ (exact)</th>
              <td className={toneClass(ni.spearman_rho)}>
                {fmtRExact(ni.spearman_rho)}{" "}
                <span className="muted">(p={fmtQ(ni.spearman_p)})</span>
              </td>
            </tr>
            <tr>
              <th>Pearson r</th>
              <td className={toneClass(ni.pearson_r)}>
                {fmtRExact(ni.pearson_r)} <span className="muted">(p={fmtQ(ni.pearson_p)})</span>
              </td>
            </tr>
            <tr>
              <th>95% CI (Pearson)</th>
              <td>{fmtCI(ni.ci_low, ni.ci_high)}</td>
            </tr>
            <tr>
              <th>FDR q</th>
              <td>{fmtQ(ni.fdr_q)}</td>
            </tr>
            <tr>
              <th>Sample size (n)</th>
              <td>
                {ni.n || "—"} · {sampleSizeLabel(ni.n)}
              </td>
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
          </tbody>
        </table>
        <p className="hint">
          <MethodologyLink topic="p-values">p-values</MethodologyLink>
          {" · "}
          <MethodologyLink topic="fdr">FDR</MethodologyLink>
          {" · "}
          <MethodologyLink topic="confidence-interval">Confidence intervals</MethodologyLink>
        </p>
      </details>

      <div className="panel">
        <h2>Revenue analysis (secondary)</h2>
        {!rev?.available ? (
          <p className="hint">
            {rev?.reason === "sector_not_comparable_revenue" ||
            row.sector === "Financials" ||
            row.sector === "Real Estate"
              ? "Revenue comparison is not used for this industry because companies report revenue-like concepts differently."
              : "No valid quarterly revenue pairs for this company."}
          </p>
        ) : (
          <>
            <p className="hint">Secondary to net income. Same-filing quarterly association.</p>
            <div className="stats">
              <div className="stat">
                <div className="label">Relationship</div>
                <div className={`rel-label ${relationshipFromRho(rev.stats?.spearman_rho).tone}`}>
                  {relationshipFromRho(rev.stats?.spearman_rho).short}
                </div>
              </div>
              <div className="stat">
                <div className="label">Spearman</div>
                <div className={`value ${toneClass(rev.stats?.spearman_rho ?? null)}`}>
                  {fmtR(rev.stats?.spearman_rho)}
                </div>
              </div>
              <div className="stat">
                <div className="label">Pearson</div>
                <div className={`value ${toneClass(rev.stats?.pearson_r ?? null)}`}>
                  {fmtR(rev.stats?.pearson_r)}
                </div>
              </div>
              <div className="stat">
                <div className="label">Sample</div>
                <div className="value-sm">{observationsPhrase(rev.stats?.n)}</div>
              </div>
            </div>
          </>
        )}
      </div>

      <details className="panel">
        <summary>
          <strong>Annual (10-K) analysis</strong>
          <span className="muted"> — secondary; not mixed into primary rankings</span>
        </summary>
        <p className="hint" style={{ marginTop: 12 }}>
          Annual samples are shorter. Shown for context only.
        </p>
        <div className="stats">
          <div className="stat">
            <div className="label">Relationship</div>
            <div className={`rel-label ${relationshipFromRho(niK?.spearman_rho).tone}`}>
              {relationshipFromRho(niK?.spearman_rho).short}
            </div>
          </div>
          <div className="stat">
            <div className="label">Spearman</div>
            <div className={`value ${toneClass(niK?.spearman_rho ?? null)}`}>
              {fmtR(niK?.spearman_rho)}
            </div>
          </div>
          <div className="stat">
            <div className="label">Pearson</div>
            <div className={`value ${toneClass(niK?.pearson_r ?? null)}`}>
              {fmtR(niK?.pearson_r)}
            </div>
          </div>
          <div className="stat">
            <div className="label">Sample</div>
            <div className="value-sm">{observationsPhrase(niK?.n)}</div>
          </div>
        </div>
      </details>

      <div className="panel">
        <h2>Filing history</h2>
        <p className="hint">Compact metrics. Quarterly rows feed the primary chart.</p>
        <div className="table-scroll">
          <h3 className="subhead">Quarterly (10-Q)</h3>
          <table>
            <thead>
              <tr>
                <th>Filing</th>
                <th>Tone</th>
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
              <h3 className="subhead">Annual (10-K)</h3>
              <table>
                <thead>
                  <tr>
                    <th>Filing</th>
                    <th>Tone</th>
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
      </div>

      {exampleRows.length ? (
        <div className="panel">
          <h2>Featured filing detail</h2>
          <p className="hint">Sentence-level tone highlights for case studies only.</p>
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
