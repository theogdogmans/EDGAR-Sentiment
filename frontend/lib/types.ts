/** Phase 5A / Phase 4 field shapes for company & sector aggregates. */

export type PreloadStatus = {
  running: boolean;
  stage: string | null;
  current: string | null;
  message: string | null;
  coverage?: {
    companies?: number;
    with_filings?: number;
    filings?: number;
    analyzed?: number;
    ready?: number;
  } | null;
};

export type ScatterPoint = {
  ticker?: string;
  accession?: string;
  form?: string | null;
  filed?: string | null;
  report_date?: string | null;
  sentiment: number | null;
  income_pct?: number | null;
  revenue_pct?: number | null;
  /** chart alias: net income YoY as percent points */
  income?: number;
};

export type MetricBlock = {
  form_type?: string | null;
  metric?: string | null;
  association_kind?: string | null;
  secondary?: boolean;
  n: number;
  spearman_rho: number | null;
  spearman_p: number | null;
  pearson_r: number | null;
  pearson_p: number | null;
  pearson_ci_low: number | null;
  pearson_ci_high: number | null;
  fdr_q: number | null;
  agreement_num: number | null;
  agreement_den: number | null;
  agreement_pct: number | null;
  agreement_label: string | null;
  reliability: string | null;
};

export type RevenueSecondary = {
  available: boolean;
  reason?: string | null;
  sector?: string | null;
  note?: string | null;
  stats: MetricBlock | null;
};

export type RankingBlock = {
  primary_metric?: string;
  public_rank_min_n?: number;
  limited_sample_min_n?: number;
  ranking_eligible_default?: boolean;
  ranking_eligible_limited?: boolean;
  ranking_insufficient?: boolean;
  sort_spearman_rho?: number | null;
  sort_pearson_r?: number | null;
  sort_agreement_pct?: number | null;
  sort_n?: number | null;
  sort_fdr_q?: number | null;
  fdr_significant?: boolean;
  fdr_significant_note?: string;
};

export type CompanyCoverage = {
  n_filings_scored?: number;
  n_10q?: number;
  n_10k?: number;
  n_10q_ni_pairs?: number;
  n_10q_revenue_pairs?: number;
};

export type SectorPrimary10Q = {
  filing_weighted_pearson_r?: number | null;
  filing_weighted_pearson_p?: number | null;
  filing_weighted_spearman_rho?: number | null;
  filing_weighted_spearman_p?: number | null;
  winsorized_pearson_r?: number | null;
  filing_n?: number | null;
  filing_weighted_agreement_label?: string | null;
  filing_weighted_agreement_rate?: number | null;
  company_balanced_pearson_r?: number | null;
  company_balanced_n_companies?: number | null;
  company_balanced_agreement_rate?: number | null;
  note?: string | null;
};

export type SectorStat = {
  sector: string;
  n_companies: number;
  n_filings: number;
  mean_sentiment: number | null;
  /** @deprecated Prefer primary_10q_ni / fw_* fields */
  r_income: number | null;
  p_income: number | null;
  n_income: number;
  r_revenue: number | null;
  p_revenue: number | null;
  n_revenue: number;
  agreement_income: number | null;
  agreement_revenue: number | null;
  points: ScatterPoint[] | null;
  payload_version?: string | null;
  primary_10q_ni?: SectorPrimary10Q | null;
  secondary_10q_revenue?: Record<string, unknown> | null;
  revenue_comparable?: boolean | null;
  revenue_unavailable_reason?: string | null;
  fw_pearson_r_10q_ni?: number | null;
  fw_spearman_rho_10q_ni?: number | null;
  fw_winsor_r_10q_ni?: number | null;
  fw_n_10q_ni?: number | null;
  cb_pearson_r_10q_ni?: number | null;
  cb_n_companies_10q_ni?: number | null;
};

export type CompanyStat = {
  ticker: string;
  display: string | null;
  name: string;
  sector: string | null;
  cik: string | null;
  n_filings: number;
  mean_sentiment: number | null;
  /** @deprecated Prefer spearman_rho_10q_ni / pearson_r_10q_ni (10-Q NI primary) */
  r_income: number | null;
  p_income: number | null;
  n_income: number;
  r_revenue: number | null;
  p_revenue: number | null;
  n_revenue: number;
  agreement_income: number | null;
  agreement_revenue: number | null;
  points: ScatterPoint[] | null;
  featured: boolean;
  payload_version?: string | null;
  coverage?: CompanyCoverage | null;
  primary_10q_ni?: MetricBlock | null;
  secondary_10q_revenue?: RevenueSecondary | null;
  secondary_10k_ni?: MetricBlock | null;
  ranking?: RankingBlock | null;
  n_10q_ni?: number | null;
  spearman_rho_10q_ni?: number | null;
  spearman_p_10q_ni?: number | null;
  pearson_r_10q_ni?: number | null;
  pearson_p_10q_ni?: number | null;
  pearson_ci_low_10q_ni?: number | null;
  pearson_ci_high_10q_ni?: number | null;
  fdr_q_10q_ni?: number | null;
  agreement_num_10q_ni?: number | null;
  agreement_den_10q_ni?: number | null;
  agreement_pct_10q_ni?: number | null;
  reliability_10q_ni?: string | null;
  ranking_eligible_default?: boolean | null;
  ranking_eligible_limited?: boolean | null;
  fdr_significant?: boolean | null;
  exclude_from_sector?: boolean | null;
};

export type ExampleFiling = {
  accession: string;
  ticker: string;
  form: string;
  filed: string | null;
  report_date: string | null;
  filing_url: string | null;
  sentiment_score: number | null;
  positive_share: number | null;
  negative_share: number | null;
  neutral_share: number | null;
  sentence_count: number | null;
  metrics: {
    revenue?: { value?: number; unit?: string; pct_change?: number | null; fp?: string } | null;
    net_income?: { value?: number; unit?: string; pct_change?: number | null; fp?: string } | null;
    operating_income?: { value?: number; unit?: string; pct_change?: number | null; fp?: string } | null;
    eps?: { value?: number; unit?: string; pct_change?: number | null; fp?: string } | null;
  } | null;
  agreement: { net_income?: boolean | null; revenue?: boolean | null } | null;
  sentences: { text: string; label: string; score: number }[] | null;
  risk_sentiment_score: number | null;
  risk_positive_share: number | null;
  risk_negative_share: number | null;
  risk_sentence_count: number | null;
  risk_sentences: { text: string; label: string; score: number }[] | null;
  role: string | null;
};
