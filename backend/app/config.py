"""Phase 3 configuration knobs (rebuild targets).

MAX_FILINGS raised from 8 → 20 so companies can accumulate ~15–18 10-Q/10-K
observations from SEC submissions ``recent`` (typically covers ~4–5 years).

Override with env ``MAX_FILINGS`` / ``PHASE3_DB_NAME``.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Phase 3 uses a dedicated DB so legacy cloud snapshots are never mixed in.
PHASE3_DB_NAME = os.getenv("PHASE3_DB_NAME", "edgar_phase3.db")
DB_PATH = DATA_DIR / PHASE3_DB_NAME

# Legacy / production path (backup reference only)
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

FINBERT_MODEL = os.getenv("FINBERT_MODEL", "ProsusAI/finbert")
SP500_CSV_URLS = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv",
)

# Sanity-check thresholds for quality log flags (do not auto-delete).
MDA_SHORT_CHARS = 1_500
MDA_LONG_CHARS = 250_000
EXTREME_NI_YOY = 5.0  # 500%
