# Phase 5B — Production release sequence (DO NOT EXECUTE until explicit approval)

## Safest ordering

**Deploy frontend AFTER data sync** (with a short maintenance window), OR:

Preferred coordinated release:

1. **Backup** live `company_stats`, `sector_stats`, `example_filings` (JSON export via REST or `pg_dump` data-only).
2. **Apply** additive migration `20260823_phase5a_production_fields.sql` on production (no drops).
3. **Verify** columns exist (`information_schema` / Supabase table editor).
4. **Sync** with `push_phase5a(dry_run=False)` only after approval:
   - company_stats (Phase 5A rows)
   - sector_stats
   - capped example_filings (clear + upsert)
5. **Verify** row counts: 502 / 11 / ~9 examples; spot-check AAPL/ADI/AMZN.
6. **Smoke-test** production API reads (anon key) for new columns.
7. **Deploy** updated frontend to Vercel (reads Phase 5A fields; preview mode off).
8. **Verify** live pages: home, leaderboard, AAPL, ADI, AMZN, MSFT, NVDA, ABBV, ADSK, methodology, one industry, one example filing.

### Why frontend after data?

Old frontend ranks `n>=3` on legacy Pearson. New data fills `r_income` from 10-Q NI but still needs Spearman/FDR UI. New frontend tolerates missing Phase 5 columns poorly if you deploy UI first against old rows.

If a blue/green is required: deploy frontend behind a flag that still works on legacy columns, then sync, then flip — not implemented; prefer sync-then-frontend for this release size.

## Rollback

1. Re-upsert backed-up `company_stats` / `sector_stats` / `example_filings` JSON.
2. Redeploy previous frontend git SHA on Vercel.
3. Leave additive columns in place (harmless); do not DROP columns in panic.

## Blockers before approval

- Production migration not applied (by design until approval)
- Upload not run (by design)
- Vercel deploy not run (by design)
- Confirm `SUPABASE_SERVICE_ROLE_KEY` available only on the secure worker host
