import Link from "next/link";
import { notFound } from "next/navigation";
import FdrBadge from "@/components/FdrBadge";
import MethodologyLink from "@/components/MethodologyLink";
import SentimentScatter from "@/components/SentimentScatter";
import StrengthBar from "@/components/StrengthBar";
import TermTip from "@/components/TermTip";
import {
  agreementSentence,
  companyTakeaway,
  observationsPhrase,
  relationshipFromRho,
  sampleSizeLabel,
} from "@/lib/explain";
import {
  fmtCI,
  fmtFilingDate,
  fmtPct,
  fmtQ,
  fmtR,
  fmtRExact,
  fmtScore,
  toneClass,
} from "@/lib/format";
import { loadCompany } from "@/lib/data";
import { formIs10K, formIs10Q, isFdrSignificant, isLimitedSample, ni10q } from "@/lib/phase5";
import { sectorSlug } from "@/lib/sector";

export const revalidate = 3600;

function secUrl(accession: string | null | undefined, cik: string | null | undefined) {
  if (!accession || !cik) return null;
  const acc = accession.replace(/-/g, "");
  const cikNum = String(cik).replace(/^0+/, "") || "0";
  return `https://www.sec.gov/Archives/edgar/data/${cikNum}/${acc}/${accession}-index.htm`;
}

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
      sentiment: Number(p.sentiment),
      income: Number((p.income_pct as number) * 100),
      revenue: p.revenue_pct == null ? null : Number(p.revenue_pct) * 100,
    }));

  const points10q = (row.points ?? []).filter((p) => formIs10Q(p.form));
  const points10k = (row.points ?? []).filter((p) => formIs10K(p.form));

  return (
    <>
      <p className="back">
        <Link href="/#explore">← Companies</Link>
        {row.sector ? (
          <>
            {" · "}
            <Link href={`/industries/${sectorSlug(row.sector)}`}>{row.sector}</Link>
          </>
        ) : null}
      </p>

      <section className="hero company-hero">
        <div className="kicker">
          {row.sector || "S&P 500"}
          {row.cik ? ` · CIK ${row.cik}` : ""}
        </div>
        <h1>
          {row.display || row.ticker}{" "}
          <span className="muted name-sub">{row.name}</span>
        </h1>
        <div className={`rel-label display ${label.tone}`}>{label.short}</div>
        <StrengthBar rho={ni.spearman_rho} tone={label.tone} />
        <p className="lede takeaway">{takeaway}</p>
        <div className="company-primary-metrics">
          <div>
            <div className="label">
              Spearman (<TermTip term="spearman">primary</TermTip>)
            </div>
            <div className={`value ${toneClass(ni.spearman_rho)}`}>{fmtR(ni.spearman_rho)}</div>
          </div>
          <div>
            <div className="label">Sample</div>
            <div className="value-sm">{observationsPhrase(ni.n, "quarterly")}</div>
            <div className="muted tiny">{sampleSizeLabel(ni.n)}</div>
          </div>
          <div>
            <div className="label">Multiple-testing check</div>
            {fdr ? (
              <FdrBadge active />
            ) : (
              <p className="muted tiny">
                Does not remain notable after adjusting for hundreds of tests.{" "}
                <MethodologyLink topic="fdr">Why? →</MethodologyLink>
              </p>
            )}
          </div>
        </div>
        <div className="secondary-stat">
          <span>
            Pearson (secondary): {fmtR(ni.pearson_r)}{" "}
            <MethodologyLink topic="correlation">Why show both? →</MethodologyLink>
          </span>
        </div>
        <p className="note">
          Contemporaneous association only — not predictive.{" "}
          <Link href="/methodology#limitations">Limitations →</Link>
        </p>
        {isLimitedSample(row) ? (
          <p className="note">Limited sample (6–7 quarters) — excluded from the default public board.</p>
        ) : null}
      </section>

      <div className="panel soft chart-panel">
        <h2>Tone vs earnings change</h2>
        <p className="hint">
          Each dot represents one 10-Q filing. Upper-right and lower-left observations indicate tone
          and earnings moving in the same direction.{" "}
          <MethodologyLink topic="scatterplots">How to read this chart →</MethodologyLink>
        </p>
        <SentimentScatter points={scatter} />
      </div>

      {agreeText ? (
        <div className="panel soft">
          <h2>Direction agreement</h2>
          <p className="lede-sm">{agreeText}</p>
          <p className="muted">
            {ni.agree_num} / {ni.agree_den} direction agreement
          </p>
          <MethodologyLink topic="agreement">How is agreement calculated? →</MethodologyLink>
        </div>
      ) : null}

      <details className="panel soft">
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
      </details>

      <details className="panel soft">
        <summary>
          <strong>Revenue analysis</strong>
          <span className="muted"> — secondary metric</span>
        </summary>
        <p className="hint" style={{ marginTop: 12 }}>
          Secondary to net income because revenue concepts are less comparable across some
          industries.
        </p>
        {!rev?.available ? (
          <div className="empty-state">
            <strong>Revenue comparison not used</strong>
            <p>
              Revenue-like concepts are not comparable enough across companies in this sector for
              the primary analysis.
            </p>
            <MethodologyLink topic="financial-data">Why? →</MethodologyLink>
          </div>
        ) : (
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
              <div className="value-sm">{observationsPhrase(rev.stats?.n, "quarterly")}</div>
            </div>
          </div>
        )}
      </details>

      <details className="panel soft">
        <summary>
          <strong>Annual 10-K analysis</strong>
          <span className="muted"> — secondary analysis</span>
        </summary>
        <p className="hint" style={{ marginTop: 12 }}>
          Annual samples are shorter and are not mixed into the default quarterly board.
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
            <div className="value-sm">{observationsPhrase(niK?.n, "annual")}</div>
          </div>
        </div>
      </details>

      <div className="panel soft">
        <h2>Filing history</h2>
        <p className="hint">Tone shown to three decimals so small nonzero values stay visible.</p>
        <div className="table-scroll">
          <h3 className="subhead">Quarterly (10-Q)</h3>
          <table className="filing-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Form</th>
                <th>Tone</th>
                <th>Net income YoY</th>
                <th>Revenue YoY</th>
              </tr>
            </thead>
            <tbody>
              {points10q.map((p, i) => {
                const href = secUrl(p.accession, row.cik);
                return (
                  <tr key={`${p.accession || p.filed}-${i}`}>
                    <td>
                      {href ? (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {fmtFilingDate(p.filed)}
                        </a>
                      ) : (
                        fmtFilingDate(p.filed)
                      )}
                    </td>
                    <td>10-Q</td>
                    <td className={toneClass(p.sentiment)}>{fmtScore(p.sentiment)}</td>
                    <td className={toneClass(p.income_pct)}>{fmtPct(p.income_pct)}</td>
                    <td className={toneClass(p.revenue_pct)}>{fmtPct(p.revenue_pct)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {points10k.length ? (
            <>
              <h3 className="subhead">Annual (10-K)</h3>
              <table className="filing-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Form</th>
                    <th>Tone</th>
                    <th>Net income YoY</th>
                    <th>Revenue YoY</th>
                  </tr>
                </thead>
                <tbody>
                  {points10k.map((p, i) => {
                    const href = secUrl(p.accession, row.cik);
                    return (
                      <tr key={`${p.accession || p.filed}-k-${i}`}>
                        <td>
                          {href ? (
                            <a href={href} target="_blank" rel="noopener noreferrer">
                              {fmtFilingDate(p.filed)}
                            </a>
                          ) : (
                            fmtFilingDate(p.filed)
                          )}
                        </td>
                        <td>10-K</td>
                        <td className={toneClass(p.sentiment)}>{fmtScore(p.sentiment)}</td>
                        <td className={toneClass(p.income_pct)}>{fmtPct(p.income_pct)}</td>
                        <td className={toneClass(p.revenue_pct)}>{fmtPct(p.revenue_pct)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          ) : null}
        </div>
      </div>

      {exampleRows.length ? (
        <div className="panel soft">
          <h2>Featured filing detail</h2>
          <p className="hint">Sentence-level tone highlights for case studies only.</p>
          <ul className="prose-list">
            {exampleRows.map((f) => (
              <li key={f.accession}>
                <Link href={`/company/${ticker}/filing/${f.accession}`}>
                  {f.form} · {fmtFilingDate(f.filed)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}
