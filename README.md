# edgar-sentiment

S&P 500 10-K / 10-Q MD&A sentiment vs the numbers in the statements.

The **website** reads a Postgres cache on [Supabase](https://supabase.com) so every lookup is a database read. A **local Python worker** still talks to SEC EDGAR and FinBERT, then upserts into that cache.

Live repo: [theogdogmans/EDGAR-Sentiment](https://github.com/theogdogmans/EDGAR-Sentiment)

## Architecture

- **Vercel / Next.js** (`frontend/`) queries Supabase with the publishable key. Public read-only RLS. No live EDGAR on the site.
- **Supabase Postgres** holds `companies`, `filings` (scores, metrics JSON, sentence highlights), and `preload_status`.
- **Local FastAPI worker** (`backend/`) downloads filings, scores MD&A, and syncs rows when `SUPABASE_SERVICE_ROLE_KEY` is set.

## Website (Vercel)

1. Import the GitHub repo in [Vercel](https://vercel.com/new).
2. Set **Root Directory** to `frontend`.
3. Add environment variables:

```
NEXT_PUBLIC_SUPABASE_URL=https://mlpqroimtfhuozmsgrtp.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_Biu6a920biHw0PFHXmHNzA_h8RPQ8lZ
```

4. Deploy.

Local UI (same cache):

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

## Fill the cache (local worker)

1. Copy `.env.example` to `.env`. Set your SEC user agent and the **service role** key from Supabase → Project Settings → API.

```
SEC_USER_AGENT=edgar-sentiment/0.1 (Josh you@example.com)
SUPABASE_URL=https://mlpqroimtfhuozmsgrtp.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

The service role never goes in the frontend or Vercel.

2. Install Python deps and run the worker:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\pip install -r backend\requirements.txt
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m app
```

That preloads S&P 500 filings and, with the service role set, upserts them to Supabase so the live site stays fast. First FinBERT pass is hours on CPU and is resumable.

Push whatever is already in the local SQLite file:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -c "from app.supabase_sync import push_all; print(push_all())"
```

## What it compares

For each recent 10-K or 10-Q: FinBERT on MD&A, XBRL YoY changes, agreement when tone and a metric move the same way. Same-filing only — not a forecast.

## Project layout

- `backend/app/edgar/` — SEC client
- `backend/app/extract/` — MD&A
- `backend/app/nlp/` — FinBERT
- `backend/app/supabase_sync.py` — upsert into Postgres
- `frontend/` — Vercel app
