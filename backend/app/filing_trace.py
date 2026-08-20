"""Per-filing stage instrumentation for Phase 3B rebuild diagnostics."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import DATA_DIR

TRACE_PATH = DATA_DIR / "phase3" / "filing_trace.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FilingTrace:
    """Logs one JSON line per stage transition / terminal outcome."""

    def __init__(
        self,
        *,
        ticker: str,
        cik: str,
        accession: str,
        form: str,
        path: Optional[Path] = None,
    ) -> None:
        self.ticker = ticker
        self.cik = cik
        self.accession = accession
        self.form = form
        self.path = path or TRACE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.t0 = time.monotonic()
        self.stage = "start"
        self.success: Optional[bool] = None
        self.exception: Optional[str] = None
        self.retry_status: Optional[str] = None

    def elapsed(self) -> float:
        return round(time.monotonic() - self.t0, 3)

    def log(
        self,
        stage: str,
        *,
        success: Optional[bool] = None,
        exception: Optional[str] = None,
        retry_status: Optional[str] = None,
        **extra: Any,
    ) -> None:
        self.stage = stage
        if success is not None:
            self.success = success
        if exception is not None:
            self.exception = exception
        if retry_status is not None:
            self.retry_status = retry_status
        row = {
            "ts": _now(),
            "ticker": self.ticker,
            "cik": self.cik,
            "accession": self.accession,
            "form": self.form,
            "stage": stage,
            "elapsed_s": self.elapsed(),
            "success": self.success,
            "exception": self.exception,
            "retry_status": self.retry_status,
            **extra,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        # Console: terminal outcomes only (jsonl has full stage detail)
        if success is False or stage in ("database_write", "skip_completed", "cache_hit"):
            print(
                f"    TRACE {self.ticker} {self.accession} stage={stage} "
                f"elapsed={row['elapsed_s']}s ok={self.success} "
                f"err={self.exception or '-'}",
                flush=True,
            )
