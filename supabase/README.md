# Supabase (industry-first cache)

Project: `mlpqroimtfhuozmsgrtp` (EDGAR-Sentiment)

## Apply schema

In the Supabase SQL editor, run [`schema.sql`](./schema.sql).

That creates:

- `sector_stats` — pooled Pearson r / agreement by GICS sector
- `company_stats` — one slim row per ticker (compact `points` JSON, no sentence blobs)
- `example_filings` — a few case studies with MD&A sentences (+ optional Item 1A bias scores)
- `preload_status` — worker progress

All tables have public `SELECT` RLS. Writes use the **service role** from the local worker only.

## Free-tier note

Do **not** sync full MD&A sentence JSON for every S&P 500 filing — that blows past the 500 MB Free database quota. Keep heavy data in local SQLite; publish aggregates with:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -c "from app.supabase_sync import push_all; print(push_all())"
```
