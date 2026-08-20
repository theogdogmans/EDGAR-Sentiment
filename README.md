# edgar-sentiment

S&P 500 10-K / 10-Q **MD&A sentiment** vs the numbers in the statements — explained by industry and company correlation.

The **website** reads slim aggregates on [Supabase](https://supabase.com) Free. A **local Python worker** talks to SEC EDGAR and FinBERT, then publishes industry/company rollups (not full sentence dumps).

Live site: [edgar-sentiment-demo.vercel.app](https://edgar-sentiment-demo.vercel.app)

Live repo: [theogdogmans/EDGAR-Sentiment](https://github.com/theogdogmans/EDGAR-Sentiment)

## Architecture

- **Vercel / Next.js** (`frontend/`) — rankings, methodology, industry and company pages. ISR reads of Postgres. No live EDGAR, no FinBERT on Vercel.
- **Supabase Postgres** — `sector_stats`, `company_stats`, `example_filings`, `preload_status` (public `SELECT` RLS). See [`supabase/schema.sql`](supabase/schema.sql).
- **Local FastAPI worker** (`backend/`) — downloads filings, scores MD&A, optional Item 1A bias demos for a few examples, upserts aggregates when `SUPABASE_SERVICE_ROLE_KEY` is set.

## What we score

- **MD&A only** (10-K Item 7 / 10-Q Item 2) with FinBERT.
- **Numbers:** same-filing YoY revenue and net income from companyfacts XBRL.
- **Not a forecast** — agreement is “did tone and the metric move the same way on this filing?”
- **Bias demo:** a handful of 10-Ks also score Item 1A Risk Factors (usually more negative) for the methodology page.

Company Pearson r with n≈8 is weak; the site headlines **industry pooled r**.

## Website (Vercel)

1. Apply [`supabase/schema.sql`](supabase/schema.sql) in the Supabase SQL editor.
2. Import the GitHub repo in [Vercel](https://vercel.com/new) (or redeploy).
3. Set **Root Directory** to `frontend`.
4. Add environment variables:

```
NEXT_PUBLIC_SUPABASE_URL=https://mlpqroimtfhuozmsgrtp.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_Biu6a920biHw0PFHXmHNzA_h8RPQ8lZ
```

5. Deploy.

Local UI:

```bash
cd frontend
cp .env.example .env.local
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

2. Install Python deps and run the worker (scores into local SQLite):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r backend/requirements.txt
export PYTHONPATH=backend
python -m app
```

3. Publish **slim aggregates** (not every sentence blob):

```bash
export PYTHONPATH=backend
python -c "from app.supabase_sync import push_all; print(push_all())"
```

First FinBERT pass is hours on CPU and is resumable. Free Supabase is 500 MB — keep full text local; cloud gets sector/company stats plus a few example filings.

## Project layout

- `backend/app/edgar/` — SEC client
- `backend/app/extract/` — MD&A + Item 1A (bias demos)
- `backend/app/nlp/` — FinBERT
- `backend/app/compare/rollup.py` — industry / company aggregates
- `backend/app/supabase_sync.py` — publish to Postgres
- `frontend/` — Vercel explainer site
- `supabase/schema.sql` — industry-first tables + RLS
