#!/usr/bin/env python3
"""Phase 3 clean rebuild runner.

Uses dedicated DB backend/data/edgar_phase3.db (default).
Does NOT push rankings to production Supabase.

Examples:
  PYTHONPATH=backend python backend/scripts/phase3_rebuild.py --priority-only
  PYTHONPATH=backend python backend/scripts/phase3_rebuild.py --all
  PYTHONPATH=backend python backend/scripts/phase3_rebuild.py --tickers AAPL,ADI,AES
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# Ensure Phase 3 DB before importing app modules that bind DB_PATH.
import os

os.environ.setdefault("PHASE3_DB_NAME", "edgar_phase3.db")

from app import db  # noqa: E402
from app.config import DB_PATH, MAX_FILINGS  # noqa: E402
from app.phase3_rebuild import (  # noqa: E402
    prioritized_tickers,
    rebuild_company,
    recompute_phase2_local,
    sector_revenue_block_stats,
)
from app.sp500 import refresh_sp500  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 clean dataset rebuild")
    parser.add_argument("--all", action="store_true", help="Process full S&P 500")
    parser.add_argument("--priority-only", action="store_true", help="Comparison tickers only")
    parser.add_argument("--tickers", type=str, default="", help="Comma-separated tickers")
    parser.add_argument("--limit", type=int, default=MAX_FILINGS, help="Filings per company")
    parser.add_argument("--skip-analyze-existing", action="store_true")
    parser.add_argument("--recompute-only", action="store_true", help="Only recompute Phase 2 stats")
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        help="Skip tickers that already have >= limit/2 scored quality_log rows",
    )
    args = parser.parse_args()

    db.init_db()
    print(f"Phase 3 DB: {DB_PATH}")
    print(f"MAX_FILINGS/target limit: {args.limit}")

    progress_path = ROOT / "backend" / "data" / "phase3_progress.json"
    report_dir = ROOT / "backend" / "data" / "phase3"
    report_dir.mkdir(parents=True, exist_ok=True)

    if args.recompute_only:
        stats = recompute_phase2_local()
        (report_dir / "phase2_recompute.json").write_text(json.dumps(stats, indent=2))
        print(json.dumps(stats, indent=2))
        return 0

    refresh_sp500()
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif args.priority_only:
        tickers = prioritized_tickers()[:14]
        # Keep only the fixed priority list that exists
        want = {
            "AAPL",
            "ADI",
            "ABBV",
            "ADSK",
            "AFL",
            "AES",
            "ADM",
            "ACN",
            "MSFT",
            "AMZN",
            "GOOGL",
            "NVDA",
            "JPM",
            "XOM",
        }
        tickers = [t for t in prioritized_tickers() if t in want]
    else:
        tickers = prioritized_tickers()

    state = {
        "started_at": _now(),
        "db": str(DB_PATH),
        "limit": args.limit,
        "tickers_total": len(tickers),
        "completed": [],
        "errors": [],
        "running": True,
    }
    progress_path.write_text(json.dumps(state, indent=2))

    t0 = time.time()
    for i, ticker in enumerate(tickers, start=1):
        if args.skip_completed:
            n_scored = sum(
                1
                for r in db.list_quality_logs()
                if r["ticker"] == ticker and r["sentiment_score"] is not None
            )
            if n_scored >= max(6, args.limit // 2):
                print(f"[{i}/{len(tickers)}] {ticker} skip (already scored={n_scored})", flush=True)
                continue
        print(f"[{i}/{len(tickers)}] {ticker} …", flush=True)
        try:
            force_analyze = not args.skip_analyze_existing
            summary = rebuild_company(
                ticker,
                limit=args.limit,
                force_filings=True,
                force_analyze=force_analyze,
            )
            state["completed"].append(
                {
                    "ticker": ticker,
                    "filings_attempted": summary["filings_attempted"],
                    "scored": summary["scored"],
                    "ni_ok": summary["ni_ok"],
                    "rev_ok": summary["rev_ok"],
                    "at": _now(),
                }
            )
            print(
                f"  attempted={summary['filings_attempted']} scored={summary['scored']} "
                f"ni_ok={summary['ni_ok']} rev_ok={summary['rev_ok']}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            err = {"ticker": ticker, "error": str(exc), "at": _now()}
            state["errors"].append(err)
            print(f"  ERROR {exc}", flush=True)
        state["current"] = ticker
        state["elapsed_s"] = round(time.time() - t0, 1)
        state["coverage"] = db.coverage()
        state["quality"] = db.quality_log_counts()
        progress_path.write_text(json.dumps(state, indent=2))

    print("Recomputing Phase 2 stats locally…", flush=True)
    phase2 = recompute_phase2_local()
    blocked = sector_revenue_block_stats()
    state.update(
        {
            "running": False,
            "finished_at": _now(),
            "elapsed_s": round(time.time() - t0, 1),
            "phase2": phase2,
            "sector_revenue_blocks": blocked,
            "quality": db.quality_log_counts(),
            "coverage": db.coverage(),
        }
    )
    progress_path.write_text(json.dumps(state, indent=2))
    (report_dir / "rebuild_summary.json").write_text(json.dumps(state, indent=2))
    print(json.dumps({k: state[k] for k in ("elapsed_s", "quality", "coverage", "phase2", "sector_revenue_blocks")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
