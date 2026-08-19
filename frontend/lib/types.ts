export type Company = {
  ticker: string;
  cik: string;
  name: string;
  display?: string;
  sector?: string;
  filings?: number;
  analyzed?: number;
  ready?: boolean;
};

export type PreloadStatus = {
  running: boolean;
  stage: string;
  current: string | null;
  message: string;
  errors?: { ticker?: string; error: string }[];
  coverage?: {
    companies: number;
    with_filings: number;
    filings: number;
    analyzed: number;
    ready: number;
  };
};

export type Metric = {
  tag: string;
  value: number;
  unit: string;
  period_end?: string;
  fy?: number;
  fp?: string;
  prior: number | null;
  prior_period_end?: string | null;
  pct_change: number | null;
} | null;

export type Sentiment = {
  score: number;
  positive_share: number;
  negative_share: number;
  neutral_share: number;
  sentence_count: number;
};

export type Agreement = {
  net_income: boolean | null;
  revenue: boolean | null;
};

export type Sentence = {
  text: string;
  label: "positive" | "negative" | "neutral" | string;
  positive: number;
  negative: number;
  neutral: number;
  score: number;
};

export type Filing = {
  accession: string;
  ticker: string;
  cik: string;
  form: string;
  filed: string;
  report_date: string;
  filing_url: string;
  analyzed: boolean;
  sentiment: Sentiment | null;
  metrics: {
    revenue: Metric;
    net_income: Metric;
    operating_income: Metric;
    eps: Metric;
  } | null;
  agreement: Agreement | null;
  sentences?: Sentence[];
  error?: string;
};

export type Correlation = {
  r: number | null;
  p_value: number | null;
  n: number;
};

export type CompanyResponse = {
  company: Company;
  filings: Filing[];
  correlation: {
    net_income: Correlation;
    revenue: Correlation;
  };
  agreement_rate: {
    net_income: number | null;
    revenue: number | null;
  };
  analyzed_count: number;
};
