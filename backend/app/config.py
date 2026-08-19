from pathlib import Path

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "edgar.db"

SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "edgar-sentiment/0.1 (Josh joshpottsjk@gmail.com)",
)
SEC_BASE = "https://data.sec.gov"
SEC_WWW = "https://www.sec.gov"
REQUEST_PAUSE_S = 0.12
MAX_FILINGS = 8
FINBERT_MODEL = os.getenv("FINBERT_MODEL", "ProsusAI/finbert")
SP500_CSV_URLS = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv",
)
