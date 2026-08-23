-- Phase 5A additive production fields for company_stats / sector_stats.
-- DO NOT remove legacy columns yet (backwards compatible until frontend migrates).
-- This file is for review only until an explicit upload/migration step is approved.

-- ---------------------------------------------------------------------------
-- company_stats: Phase 4 primary ranking + coverage mirrors
-- ---------------------------------------------------------------------------
ALTER TABLE company_stats
  ADD COLUMN IF NOT EXISTS payload_version TEXT,
  ADD COLUMN IF NOT EXISTS coverage JSONB,
  ADD COLUMN IF NOT EXISTS primary_10q_ni JSONB,
  ADD COLUMN IF NOT EXISTS secondary_10q_revenue JSONB,
  ADD COLUMN IF NOT EXISTS secondary_10k_ni JSONB,
  ADD COLUMN IF NOT EXISTS ranking JSONB,
  ADD COLUMN IF NOT EXISTS n_10q_ni INTEGER,
  ADD COLUMN IF NOT EXISTS spearman_rho_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS spearman_p_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS pearson_r_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS pearson_p_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS pearson_ci_low_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS pearson_ci_high_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS fdr_q_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS agreement_num_10q_ni INTEGER,
  ADD COLUMN IF NOT EXISTS agreement_den_10q_ni INTEGER,
  ADD COLUMN IF NOT EXISTS agreement_pct_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS reliability_10q_ni TEXT,
  ADD COLUMN IF NOT EXISTS ranking_eligible_default BOOLEAN,
  ADD COLUMN IF NOT EXISTS ranking_eligible_limited BOOLEAN,
  ADD COLUMN IF NOT EXISTS fdr_significant BOOLEAN,
  ADD COLUMN IF NOT EXISTS exclude_from_sector BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS legacy_note TEXT,
  ADD COLUMN IF NOT EXISTS stats_phase2 JSONB;

-- Helpful indexes for the eventual Phase 4-aware UI (n>=8 default board)
CREATE INDEX IF NOT EXISTS company_stats_rank_default_spearman_idx
  ON company_stats (spearman_rho_10q_ni DESC NULLS LAST)
  WHERE ranking_eligible_default IS TRUE;

CREATE INDEX IF NOT EXISTS company_stats_fdr_sig_idx
  ON company_stats (fdr_q_10q_ni ASC NULLS LAST)
  WHERE fdr_significant IS TRUE;

CREATE INDEX IF NOT EXISTS company_stats_n_10q_ni_idx
  ON company_stats (n_10q_ni DESC NULLS LAST);

-- ---------------------------------------------------------------------------
-- sector_stats: dual-weight 10-Q NI fields
-- ---------------------------------------------------------------------------
ALTER TABLE sector_stats
  ADD COLUMN IF NOT EXISTS payload_version TEXT,
  ADD COLUMN IF NOT EXISTS primary_10q_ni JSONB,
  ADD COLUMN IF NOT EXISTS secondary_10q_revenue JSONB,
  ADD COLUMN IF NOT EXISTS revenue_comparable BOOLEAN,
  ADD COLUMN IF NOT EXISTS revenue_unavailable_reason TEXT,
  ADD COLUMN IF NOT EXISTS fw_pearson_r_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS fw_spearman_rho_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS fw_winsor_r_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS fw_n_10q_ni INTEGER,
  ADD COLUMN IF NOT EXISTS cb_pearson_r_10q_ni DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS cb_n_companies_10q_ni INTEGER,
  ADD COLUMN IF NOT EXISTS legacy_note TEXT,
  ADD COLUMN IF NOT EXISTS stats_phase2 JSONB;

-- Legacy columns intentionally retained:
--   company_stats: r_income, p_income, n_income, r_revenue, p_revenue, n_revenue,
--                  agreement_income, agreement_revenue, points, featured
--   sector_stats:  r_income, p_income, n_income, r_revenue, p_revenue, n_revenue,
--                  agreement_income, agreement_revenue, points
-- Do not DROP them in this migration.
