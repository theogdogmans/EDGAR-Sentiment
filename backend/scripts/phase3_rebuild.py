#!/usr/bin/env python3
"""Phase 3 clean rebuild runner (3B: registrant dedupe, resume, isolation).

Uses dedicated DB backend/data/edgar_phase3.db (default).
Does NOT push rankings to production Supabase.

Examples:
  PYTHONPATH=backend python backend/scripts/phase3_rebuild.py --priority-only
  PYTHONPATH=backend python backend/scripts/phase3_rebuild.py --all --skip-completed
  PYTHONPATH=backend python backend/scripts/phase3_rebuild.py --tickers AAPL,XOM
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("PHASE3_DB_NAME", "edgar_phase3.db")

from app import db  # noqa: E402
from app.config import DB_PATH, MAX_FILINGS  # noqa: E402
from app.phase3_rebuild import (  # noqa: E402
    order_registrants_for_rebuild,
    prioritized_tickers,
    rebuild_company,
    rebuild_registrant,
    recompute_phase2_local,
    sector_revenue_block_stats,
)
from app.registrants import registrant_plan  # noqa: E402
from app.sp500 import refresh_sp500  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 clean dataset rebuild")
    parser.add_argument("--all", action="store_true", help="Process full S&P 500 (unique CIKs)")
    parser.add_argument("--priority-only", action="store_true", help="Comparison tickers only")
    parser.add_argument("--tickers", type=str, default="", help="Comma-separated tickers")
    parser.add_argument("--limit", type=int, default=MAX_FILINGS, help="Filings per company")
    parser.add_argument(
        "--force-analyze",
        action="store_true",
        help="Re-run FinBERT even when analyses already exist (default: skip completed)",
    )
    parser.add_argument("--skip-analyze-existing", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--recompute-only", action="store_true", help="Only recompute Phase 2 stats")
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        help="Skip filings (and registrants) already complete; resume unfinished work",
    )
    parser.add_argument(
        "--empty-first",
        action="store_true",
        default=True,
        help="Process registrants with zero completed filings first (default on)",
    )
    parser.add_argument("--no-empty-first", action="store_true", help="Alphabetical registrant order")
    parser.add_argument(
        "--by-ticker",
        action="store_true",
        help="Legacy per-ticker loop (no CIK dedupe). Default is registrant/CIK plan.",
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
    skip_completed = bool(args.skip_completed or args.skip_analyze_existing)
    force_analyze = bool(args.force_analyze)

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif args.priority_only:
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

    prefer_empty = not args.no_empty_first
    state = {
        "started_at": _now(),
        "db": str(DB_PATH),
        "limit": args.limit,
        "skip_completed": skip_completed,
        "force_analyze": force_analyze,
        "mode": "by_ticker" if args.by_ticker else "registrant",
        "tickers_requested": len(tickers),
        "completed": [],
        "skipped_aliases": [],
        "errors": [],
        "running": True,
    }
    progress_path.write_text(json.dumps(state, indent=2))

    t0 = time.time()

    if args.by_ticker:
        work = [{"canonical_ticker": t, "alias_tickers": [], "member_tickers": [t]} for t in tickers]
        if prefer_empty:
            work = order_registrants_for_rebuild(work, prefer_empty_first=True)
    else:
        plan = registrant_plan(tickers)
        work = order_registrants_for_rebuild(plan, prefer_empty_first=prefer_empty)
        # Record aliases that are membership-only
        for item in plan:
            for a in item.get("alias_tickers") or []:
                state["skipped_aliases"].append(
                    {"alias": a, "canonical": item["canonical_ticker"], "cik": item["cik"]}
                )

    state["registrants_total"] = len(work)
    print(
        f"Work items: {len(work)} unique registrants "
        f"(from {len(tickers)} tickers; aliases={len(state['skipped_aliases'])})",
        flush=True,
    )

    for i, item in enumerate(work, start=1):
        ticker = item["canonical_ticker"]
        if skip_completed and not force_analyze:
            n_done = db.count_completed_analyses_for_ticker(ticker)
            for m in item.get("member_tickers") or []:
                n_done = max(n_done, db.count_completed_analyses_for_ticker(m))
            # Registrant considered done if enough analyses exist for the limit target
            if n_done >= max(6, args.limit // 2):
                # Still refresh filings list if thin, but skip FinBERT via skip_completed
                pass

        aliases = item.get("alias_tickers") or []
        alias_note = f" aliases={aliases}" if aliases else ""
        print(f"[{i}/{len(work)}] {ticker}{alias_note} …", flush=True)
        try:
            if args.by_ticker:
                summary = rebuild_company(
                    ticker,
                    limit=args.limit,
                    force_filings=True,
                    force_analyze=force_analyze,
                    skip_completed=skip_completed and not force_analyze,
                )
            else:
                summary = rebuild_registrant(
                    item,
                    limit=args.limit,
                    force_filings=True,
                    force_analyze=force_analyze,
                    skip_completed=skip_completed and not force_analyze,
                )
            state["completed"].append(
                {
                    "ticker": ticker,
                    "cik": summary.get("cik"),
                    "cik_resolution": summary.get("cik_resolution"),
                    "filings_attempted": summary["filings_attempted"],
                    "scored": summary["scored"],
                    "ni_ok": summary["ni_ok"],
                    "rev_ok": summary["rev_ok"],
                    "errors": summary.get("errors") or [],
                    "at": _now(),
                }
            )
            print(
                f"  attempted={summary['filings_attempted']} scored={summary['scored']} "
                f"ni_ok={summary['ni_ok']} rev_ok={summary['rev_ok']} "
                f"cik={summary.get('cik')} res={summary.get('cik_resolution')}",
                flush=True,
            )
            if summary.get("company_failed"):
                state["errors"].append(
                    {"ticker": ticker, "error": (summary.get("errors") or ["company_failed"])[0], "at": _now()}
                )
        except Exception as exc:  # noqa: BLE001
            err = {"ticker": ticker, "error": str(exc), "at": _now()}
            state["errors"].append(err)
            print(f"  ERROR {exc}", flush=True)
        state["current"] = ticker
        state["elapsed_s"] = round(time.time() - t0, 1)
        state["coverage"] = db.coverage()
        state["quality"] = db.quality_log_counts()
        state["jobs"] = db.filing_job_status_counts()
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
            "jobs": db.filing_job_status_counts(),
        }
    )
    progress_path.write_text(json.dumps(state, indent=2))
    (report_dir / "rebuild_summary.json").write_text(json.dumps(state, indent=2))
    print(
        json.dumps(
            {
                k: state[k]
                for k in (
                    "elapsed_s",
                    "quality",
                    "coverage",
                    "jobs",
                    "phase2",
                    "sector_revenue_blocks",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
