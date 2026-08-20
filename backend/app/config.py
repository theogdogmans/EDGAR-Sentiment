"""HTTP / rebuild resilience knobs for Phase 3B."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PHASE3_DB_NAME = os.getenv("PHASE3_DB_NAME", "edgar_phase3.db")
DB_PATH = DATA_DIR / PHASE3_DB_NAME
LEGACY_DB_PATH = DATA_DIR / "edgar.db"

SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "edgar-sentiment/0.1 (Josh joshpottsjk@gmail.com)",
)
SEC_BASE = "https://data.sec.gov"
SEC_WWW = "https://www.sec.gov"
REQUEST_PAUSE_S = float(os.getenv("REQUEST_PAUSE_S", "0.12"))

# Target historical depth for research usefulness (was 8).
MAX_FILINGS = int(os.getenv("MAX_FILINGS", "20"))

# HTTP / retry policy — prevent infinite hangs and retry storms.
HTTP_TIMEOUT_S = float(os.getenv("HTTP_TIMEOUT_S", "60"))
HTTP_DOWNLOAD_TIMEOUT_S = float(os.getenv("HTTP_DOWNLOAD_TIMEOUT_S", "90"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "2"))
FILING_SOFT_TIMEOUT_S = float(os.getenv("FILING_SOFT_TIMEOUT_S", "600"))  # 10 min/filing
FILING_MAX_ATTEMPTS = int(os.getenv("FILING_MAX_ATTEMPTS", "2"))
TICKER_MAX_FAILURES = int(os.getenv("TICKER_MAX_FAILURES", "8"))

# If mapped CIK has fewer than this many 10-K/10-Q in recent+shards probe,
# attempt accession-prefix / alternate-CIK recovery (XOM Holdings case).
MIN_CIK_HISTORY = int(os.getenv("MIN_CIK_HISTORY", "6"))

FINBERT_MODEL = os.getenv("FINBERT_MODEL", "ProsusAI/finbert")
SP500_CSV_URLS = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv",
)

MDA_SHORT_CHARS = 1_500
MDA_LONG_CHARS = 250_000
EXTREME_NI_YOY = 5.0
