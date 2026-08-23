import type { CompanyStat } from "./types";

export const PUBLIC_RANK_N = 8;
export const LIMITED_RANK_N = 6;

export const CASE_STUDIES = ["AAPL", "ADI", "AMZN", "MSFT", "NVDA"] as const;

export type LeaderboardSort =
  | "spearman"
  | "pearson"
  | "agreement"
  | "n"
  | "q";

export type LeaderboardFilter = "all" | "fdr" | "positive" | "negative" | "high_agreement";

/** Prefer Phase 5A flat fields; fall back to nested primary_10q_ni. */
export function ni10q(c: CompanyStat) {
  const nested = c.primary_10q_ni;
  return {
    n: c.n_10q_ni ?? nested?.n ?? c.n_income ?? 0,
    spearman_rho: c.spearman_rho_10q_ni ?? nested?.spearman_rho ?? null,
    spearman_p: c.spearman_p_10q_ni ?? nested?.spearman_p ?? null,
    pearson_r: c.pearson_r_10q_ni ?? nested?.pearson_r ?? c.r_income ?? null,
    pearson_p: c.pearson_p_10q_ni ?? nested?.pearson_p ?? c.p_income ?? null,
    ci_low: c.pearson_ci_low_10q_ni ?? nested?.pearson_ci_low ?? null,
    ci_high: c.pearson_ci_high_10q_ni ?? nested?.pearson_ci_high ?? null,
    fdr_q: c.fdr_q_10q_ni ?? nested?.fdr_q ?? null,
    agree_num: c.agreement_num_10q_ni ?? nested?.agreement_num ?? null,
    agree_den: c.agreement_den_10q_ni ?? nested?.agreement_den ?? null,
    agree_pct: c.agreement_pct_10q_ni ?? nested?.agreement_pct ?? null,
    agree_label: nested?.agreement_label ?? null,
    reliability: c.reliability_10q_ni ?? nested?.reliability ?? null,
  };
}

export function isDefaultEligible(c: CompanyStat): boolean {
  if (c.ranking_eligible_default != null) return Boolean(c.ranking_eligible_default);
  if (c.ranking?.ranking_eligible_default != null) return Boolean(c.ranking.ranking_eligible_default);
  const n = ni10q(c).n;
  return n >= PUBLIC_RANK_N && ni10q(c).pearson_r != null;
}

export function isLimitedSample(c: CompanyStat): boolean {
  if (c.ranking_eligible_limited != null) return Boolean(c.ranking_eligible_limited);
  const n = ni10q(c).n;
  return n >= LIMITED_RANK_N && n < PUBLIC_RANK_N && ni10q(c).pearson_r != null;
}

export function isFdrSignificant(c: CompanyStat): boolean {
  if (c.fdr_significant != null) return Boolean(c.fdr_significant);
  if (c.ranking?.fdr_significant != null) return Boolean(c.ranking.fdr_significant);
  const q = ni10q(c).fdr_q;
  return q != null && q < 0.05;
}

export function sortCompanies(
  rows: CompanyStat[],
  sort: LeaderboardSort = "spearman",
  dir: "desc" | "asc" = "desc"
): CompanyStat[] {
  const eligible = rows.filter(isDefaultEligible);
  const mul = dir === "desc" ? 1 : -1;
  eligible.sort((a, b) => {
    const aa = ni10q(a);
    const bb = ni10q(b);
    let av: number | null = null;
    let bv: number | null = null;
    switch (sort) {
      case "spearman":
        av = aa.spearman_rho;
        bv = bb.spearman_rho;
        break;
      case "pearson":
        av = aa.pearson_r;
        bv = bb.pearson_r;
        break;
      case "agreement":
        av = aa.agree_pct;
        bv = bb.agree_pct;
        break;
      case "n":
        av = aa.n;
        bv = bb.n;
        break;
      case "q":
        // Lower q is "stronger" for desc
        av = aa.fdr_q;
        bv = bb.fdr_q;
        if (av == null && bv == null) return a.ticker.localeCompare(b.ticker);
        if (av == null) return 1;
        if (bv == null) return -1;
        return (av - bv) * (dir === "desc" ? 1 : -1);
    }
    if (av == null && bv == null) return a.ticker.localeCompare(b.ticker);
    if (av == null) return 1;
    if (bv == null) return -1;
    return (bv - av) * mul;
  });
  return eligible;
}

export function filterCompanies(rows: CompanyStat[], filter: LeaderboardFilter): CompanyStat[] {
  switch (filter) {
    case "fdr":
      return rows.filter(isFdrSignificant);
    case "positive":
      return rows.filter((c) => {
        const r = ni10q(c).spearman_rho;
        return r != null && r > 0;
      });
    case "negative":
      return rows.filter((c) => {
        const r = ni10q(c).spearman_rho;
        return r != null && r < 0;
      });
    case "high_agreement":
      return rows.filter((c) => {
        const p = ni10q(c).agree_pct;
        const den = ni10q(c).agree_den;
        return p != null && p >= 75 && (den == null || den >= 5);
      });
    default:
      return rows;
  }
}

export function formIs10Q(form: string | null | undefined): boolean {
  return Boolean(form && String(form).toUpperCase().startsWith("10-Q"));
}

export function formIs10K(form: string | null | undefined): boolean {
  return Boolean(form && String(form).toUpperCase().startsWith("10-K"));
}
