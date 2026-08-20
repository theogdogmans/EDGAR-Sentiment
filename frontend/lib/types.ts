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
  sentiment: number | null;
  income_pct?: number | null;
  revenue_pct?: number | null;
  /** chart alias: net income YoY as percent points */
  income?: number;
};

export type SectorStat = {
  sector: string;
  n_companies: number;
  n_filings: number;
  mean_sentiment: number | null;
  r_income: number | null;
  p_income: number | null;
  n_income: number;
  r_revenue: number | null;
  p_revenue: number | null;
  n_revenue: number;
  agreement_income: number | null;
  agreement_revenue: number | null;
  points: ScatterPoint[] | null;
};

export type CompanyStat = {
  ticker: string;
  display: string | null;
  name: string;
  sector: string | null;
  cik: string | null;
  n_filings: number;
  mean_sentiment: number | null;
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
