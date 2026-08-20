# Mac → Windows (RTX 3080 Ti) transfer — Phase 3 checkpoint resume

This repo includes a **Git LFS** SQLite checkpoint of the Phase 3 rebuild stopped on the MacBook.
Do **not** publish to production Supabase during the rebuild.

Tag: `mac-to-windows-transfer`  
Transfer DB (LFS): `backend/data/transfer/edgar_phase3_transfer.db`

---

## 1. Prerequisites (Windows)

- Git for Windows **with Git LFS**
- Python 3.10+ (3.11 recommended)
- NVIDIA driver for RTX 3080 Ti
- CUDA-capable PyTorch (install step below)

Install Git LFS if missing:

```powershell
git lfs version
# If missing: https://git-lfs.com  then:
git lfs install
```

---

## 2. Clone and checkout

```powershell
cd $env:USERPROFILE\Projects   # or your preferred folder
git clone https://github.com/theogdogmans/EDGAR-Sentiment.git
cd EDGAR-Sentiment
git fetch --tags
git checkout mac-to-windows-transfer
# Or stay on main after pull if the transfer commit is already merged:
# git checkout main
# git pull
git lfs pull
```

Confirm the transfer DB downloaded as a real file (~417 MB), not a tiny pointer:

```powershell
Get-Item backend\data\transfer\edgar_phase3_transfer.db | Select-Object FullName, Length
# Length should be roughly 400000000+ bytes
```

---

## 3. Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### Install PyTorch with CUDA (3080 Ti)

Pick a CUDA build that matches your driver. Common choice:

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

If that fails, try `cu121` instead of `cu124`.

Then project deps:

```powershell
pip install -r backend\requirements.txt
```

---

## 4. Environment file (no secrets in git)

```powershell
Copy-Item .env.example .env
notepad .env
```

Set at least:

- `SEC_USER_AGENT` — your name + email (SEC requirement)
- `PHASE3_DB_NAME=edgar_phase3.db`

Leave `SUPABASE_SERVICE_ROLE_KEY` empty unless you intentionally sync later. **Phase 3 must not publish.**

---

## 5. Restore the Phase 3 checkpoint database

```powershell
New-Item -ItemType Directory -Force -Path backend\data | Out-Null
Copy-Item backend\data\transfer\edgar_phase3_transfer.db backend\data\edgar_phase3.db -Force
# Ensure no stale WAL from a previous attempt:
Remove-Item backend\data\edgar_phase3.db-wal, backend\data\edgar_phase3.db-shm -ErrorAction SilentlyContinue
```

---

## 6. Verify SQLite integrity + checkpoint counts

```powershell
$env:PYTHONPATH = "backend"
$env:PHASE3_DB_NAME = "edgar_phase3.db"
python -c @"
import sqlite3, json
from pathlib import Path
p = Path('backend/data/edgar_phase3.db')
c = sqlite3.connect(p)
print('integrity', c.execute('PRAGMA integrity_check').fetchone()[0])
print('analyses', c.execute('SELECT COUNT(*) FROM analyses').fetchone()[0])
print('quality_scored', c.execute('SELECT COUNT(*) FROM quality_log WHERE sentiment_score IS NOT NULL').fetchone()[0])
print('jobs_complete', c.execute(\"SELECT COUNT(*) FROM filing_jobs WHERE status='complete'\").fetchone()[0])
print('tickers_with_analyses', c.execute('SELECT COUNT(DISTINCT f.ticker) FROM filings f JOIN analyses a ON a.accession=f.accession').fetchone()[0])
print('distinct_ciks', c.execute('SELECT COUNT(DISTINCT cik) FROM filings').fetchone()[0])
meta = Path('backend/data/transfer/checkpoint_meta.json')
if meta.exists():
    print('meta', meta.read_text()[:500])
"@
```

Expected ballpark at transfer time:

- integrity: `ok`
- analyses / quality_scored / jobs_complete: **1110**
- tickers with analyses / distinct CIKs: **65**

---

## 7. Run the test suite

```powershell
$env:PYTHONPATH = "backend"
python -m pytest backend\tests -q
```

All tests should pass (Phase 1 + 2 + 3B resilience).

---

## 8. Verify NVIDIA CUDA / PyTorch

```powershell
python -c "import torch; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('cuda_version', torch.version.cuda); print('gpu_name', torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

You want:

- `cuda_available True`
- a CUDA version string (not `None`)
- `gpu_name` containing `3080 Ti` (or your NVIDIA device)

If `cuda_available` is `False`, reinstall the CUDA wheel of torch before resuming FinBERT work.

FinBERT auto-selects CUDA when available (`backend/app/nlp/finbert.py`).

---

## 9. Resume Phase 3 (skip completed filings)

Do **not** use `--force-analyze`. Use `--skip-completed` so finished accessions are not re-scored.

```powershell
$env:PYTHONPATH = "backend"
$env:PHASE3_DB_NAME = "edgar_phase3.db"
python -u backend\scripts\phase3_rebuild.py --all --limit 20 --skip-completed
```

Progress is written to `backend\data\phase3_progress.json`.  
Per-filing stage traces append to `backend\data\phase3\filing_trace.jsonl`.

When the full run finishes:

```powershell
python -u backend\scripts\phase3_rebuild.py --recompute-only
python -u backend\scripts\phase3_compare_report.py
```

Still **do not** push rankings to production Supabase until you decide to.

---

## Notes

- Share-class tickers (GOOG/GOOGL, FOX/FOXA, NWS/NWSA) are processed once per SEC CIK.
- XOM maps through CIK history recovery to EXXON MOBIL CORP (`0000034088`).
- Live working DB stays gitignored; only `backend/data/transfer/*` is committed via LFS.
- Never commit `.env`, `.venv`, Hugging Face caches, or `*.db-wal` / `*.db-shm`.
