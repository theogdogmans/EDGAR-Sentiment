-- Industry-first schema for free Supabase (keep under ~50 MB).
-- Full filing text + FinBERT scores stay in local SQLite; cloud gets aggregates.

-- Progress from the local worker
CREATE TABLE IF NOT EXISTS preload_status (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  running BOOLEAN NOT NULL DEFAULT false,
  stage TEXT,
  current TEXT,
  message TEXT,
  coverage JSONB,
  updated_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO preload_status (id, running, stage, message)
VALUES (1, false, 'idle', 'Waiting for local worker')
ON CONFLICT (id) DO NOTHING;

-- One row per GICS sector (pooled across companies)
CREATE TABLE IF NOT EXISTS sector_stats (
  sector TEXT PRIMARY KEY,
  n_companies INTEGER NOT NULL DEFAULT 0,
  n_filings INTEGER NOT NULL DEFAULT 0,
  mean_sentiment DOUBLE PRECISION,
  r_income DOUBLE PRECISION,
  p_income DOUBLE PRECISION,
  n_income INTEGER NOT NULL DEFAULT 0,
  r_revenue DOUBLE PRECISION,
  p_revenue DOUBLE PRECISION,
  n_revenue INTEGER NOT NULL DEFAULT 0,
  agreement_income DOUBLE PRECISION,
  agreement_revenue DOUBLE PRECISION,
  points JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- One row per S&P 500 ticker (slim; no sentence blobs)
CREATE TABLE IF NOT EXISTS company_stats (
  ticker TEXT PRIMARY KEY,
  display TEXT,
  name TEXT NOT NULL,
  sector TEXT,
  cik TEXT,
  n_filings INTEGER NOT NULL DEFAULT 0,
  mean_sentiment DOUBLE PRECISION,
  r_income DOUBLE PRECISION,
  p_income DOUBLE PRECISION,
  n_income INTEGER NOT NULL DEFAULT 0,
  r_revenue DOUBLE PRECISION,
  p_revenue DOUBLE PRECISION,
  n_revenue INTEGER NOT NULL DEFAULT 0,
  agreement_income DOUBLE PRECISION,
  agreement_revenue DOUBLE PRECISION,
  points JSONB NOT NULL DEFAULT '[]'::jsonb,
  featured BOOLEAN NOT NULL DEFAULT false,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS company_stats_sector_idx ON company_stats (sector);
CREATE INDEX IF NOT EXISTS company_stats_r_income_idx ON company_stats (r_income DESC NULLS LAST);

-- Only a handful of case-study filings with sentence highlights (+ optional Item 1A bias demo)
CREATE TABLE IF NOT EXISTS example_filings (
  accession TEXT PRIMARY KEY,
  ticker TEXT NOT NULL REFERENCES company_stats (ticker) ON DELETE CASCADE,
  form TEXT NOT NULL,
  filed TEXT,
  report_date TEXT,
  filing_url TEXT,
  sentiment_score DOUBLE PRECISION,
  positive_share DOUBLE PRECISION,
  negative_share DOUBLE PRECISION,
  neutral_share DOUBLE PRECISION,
  sentence_count INTEGER,
  metrics JSONB,
  agreement JSONB,
  sentences JSONB NOT NULL DEFAULT '[]'::jsonb,
  risk_sentiment_score DOUBLE PRECISION,
  risk_positive_share DOUBLE PRECISION,
  risk_negative_share DOUBLE PRECISION,
  risk_sentence_count INTEGER,
  risk_sentences JSONB,
  role TEXT,
  analyzed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS example_filings_ticker_idx ON example_filings (ticker);

-- Public read-only for the Vercel site (publishable / anon key)
ALTER TABLE preload_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE sector_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE example_filings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read preload_status" ON preload_status;
CREATE POLICY "Public read preload_status" ON preload_status FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read sector_stats" ON sector_stats;
CREATE POLICY "Public read sector_stats" ON sector_stats FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read company_stats" ON company_stats;
CREATE POLICY "Public read company_stats" ON company_stats FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read example_filings" ON example_filings;
CREATE POLICY "Public read example_filings" ON example_filings FOR SELECT USING (true);

-- Optional: drop legacy heavy tables if migrating an older project
-- DROP TABLE IF EXISTS filings;
-- DROP TABLE IF EXISTS companies;
