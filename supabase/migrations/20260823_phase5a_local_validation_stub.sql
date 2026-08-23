-- Disposable local validation schema for Phase 5A migration review.
-- Not production. Apply with: psql $DATABASE_URL -f this_file (optional).
-- Or: sqlite emulation is insufficient for JSONB — use Postgres when available.

BEGIN;

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

COMMIT;

-- Then apply: supabase/migrations/20260823_phase5a_production_fields.sql
-- Validate with information_schema / \\d company_stats
-- Roll back disposable DB afterward. Never run against production from this file.
