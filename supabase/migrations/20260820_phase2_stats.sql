-- Additive Phase 2 columns. Safe to apply without changing production UI reads.
-- Does not transform or overwrite raw YoY observations.

ALTER TABLE company_stats
  ADD COLUMN IF NOT EXISTS stats_phase2 JSONB;

ALTER TABLE sector_stats
  ADD COLUMN IF NOT EXISTS stats_phase2 JSONB;
