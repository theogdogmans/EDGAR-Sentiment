# Phase 5B — Pre-Upload Report

**STOP:** No production migration, no Supabase upload, no Vercel deploy.

## Checklist

| Item | Status |
|---|---|
| A. Sync bug fixed (`null` → safe delete) | **Yes** |
| B. Phase 5A sync path ready (`push_phase5a`) | **Yes** (defaults `dry_run=True`) |
| C. Migration validated (additive-only) | **Yes** (not executed on prod) |
| D. Frontend updated | **Yes** |
| E. Legacy labels removed / replaced | **Yes** |
| F. Methodology updated | **Yes** |
| G. Preview QA | **Pass** (`DATA_SOURCE=phase5_preview`) |
| H. Case-study values | **Match Phase 4** |
| I. Tests passed | **5/5** `test_phase5b_sync.py` |
| J. Build passed | **Yes** (`next build` exit 0) |
| K. Production release order | See `PRODUCTION_RELEASE_PLAN.md` |
| L. Rollback plan | Backup JSON → re-upsert → redeploy prior frontend |
| M. Blockers | Explicit approval required for migration + upload + deploy |

## Exact values (preview payload)

| Ticker | n | ρ | r | q | FDR | Agree |
|---|---:|---:|---:|---:|---|---|
| AAPL | 15 | 0.854 | 0.766 | 0.019 | yes | 6/8 |
| ADI | 15 | 0.775 | 0.765 | 0.019 | yes | 8/8 |
| AMZN | 15 | −0.525 | −0.614 | 0.105 | no | 4/15 |
| MSFT | 15 | 0.436 | 0.568 | 0.159 | no | 13/15 |
| NVDA | 15 | 0.636 | 0.402 | 0.399 | no | **13/13** |
| ABBV | 15 | ~0 | ~0 | 0.947 | no | 7/15 |
| ADSK | 15 | ~0 | ~0 | 0.947 | no | 9/10 |

## Proposed release order

1. Backup live rows  
2. Apply additive migration  
3. Verify columns  
4. `push_phase5a(dry_run=False)`  
5. Verify counts + spot checks  
6. Deploy frontend  
7. Live smoke tests  

**Frontend after data sync** minimizes mismatch.

## Rollback

Re-upsert backup JSON; redeploy previous frontend SHA; leave additive columns.
