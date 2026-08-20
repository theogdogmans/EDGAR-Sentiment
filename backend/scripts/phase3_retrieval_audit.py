#!/usr/bin/env python3
"""Retrieval-only S&P 500 coverage audit (no FinBERT).

Writes backend/data/phase3/retrieval_audit.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("PHASE3_DB_NAME", "edgar_phase3.db")

from app import db  # noqa: E402
from app.config import MAX_FILINGS  # noqa: E402
from app.edgar.client import collect_10k_10q_for_cik, resolve_ticker  # noqa: E402
from app.registrants import duplicate_cik_groups, registrant_plan  # noqa: E402
from app.sp500 import refresh_sp500  # noqa: E402


def audit_one(ticker: str, limit: int = MAX_FILINGS) -> dict:
    t0 = time.monotonic()
    sp = db.get_sp500(ticker)
    company = resolve_ticker(ticker, validate_history=True)
    rows = collect_10k_10q_for_cik(company["cik"], ticker=company["ticker"], limit=limit)
    n_q = sum(1 for r in rows if r["form"] == "10-Q")
    n_k = sum(1 for r in rows if r["form"] == "10-K")
    used_shard = bool(rows and rows[0].get("_used_archive_shard"))
    return {
        "ticker": company["ticker"],
        "cik": company["cik"],
        "company": company.get("name"),
        "sector": None if sp is None else sp["sector"],
        "n_10q": n_q,
        "n_10k": n_k,
        "total_eligible": len(rows),
        "archive_shard_used": used_shard,
        "cik_resolution": company.get("cik_resolution"),
        "mapped_cik_thin": company.get("mapped_cik_thin"),
        "elapsed_s": round(time.monotonic() - t0, 3),
        "oldest": rows[-1]["filed"] if rows else None,
        "newest": rows[0]["filed"] if rows else None,
    }


def main() -> int:
    db.init_db()
    refresh_sp500()
    plan = registrant_plan()
    dups = duplicate_cik_groups()
    dup_ciks = {g["cik"] for g in dups}
    alias_of = {}
    for g in dups:
        for a in g["aliases"]:
            alias_of[a] = g["canonical_ticker"]

    rows = []
    # Audit unique CIKs (canonical) plus note aliases
    for i, item in enumerate(plan, start=1):
        t = item["canonical_ticker"]
        print(f"[{i}/{len(plan)}] audit {t} …", flush=True)
        try:
            row = audit_one(t)
            row["duplicate_cik"] = item["cik"] in dup_ciks
            row["alias_tickers"] = item.get("alias_tickers") or []
            row["member_tickers"] = item.get("member_tickers") or [t]
            rows.append(row)
            print(
                f"  total={row['total_eligible']} 10-Q={row['n_10q']} 10-K={row['n_10k']} "
                f"shard={row['archive_shard_used']} cik={row['cik']} res={row['cik_resolution']}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {t}: {exc}", flush=True)
            rows.append(
                {
                    "ticker": t,
                    "error": str(exc),
                    "total_eligible": 0,
                    "n_10q": 0,
                    "n_10k": 0,
                    "duplicate_cik": item["cik"] in dup_ciks,
                    "alias_tickers": item.get("alias_tickers") or [],
                }
            )

    flags = {
        "lt_10_total": [r["ticker"] for r in rows if int(r.get("total_eligible") or 0) < 10],
        "lt_6_10q": [r["ticker"] for r in rows if int(r.get("n_10q") or 0) < 6],
        "only_1": [r["ticker"] for r in rows if int(r.get("total_eligible") or 0) == 1],
        "zero": [r["ticker"] for r in rows if int(r.get("total_eligible") or 0) == 0],
    }
    hist = Counter(int(r.get("total_eligible") or 0) for r in rows)
    out = {
        "registrants": len(rows),
        "duplicate_cik_groups": dups,
        "flags": flags,
        "total_eligible_histogram": dict(sorted(hist.items())),
        "rows": rows,
    }
    path = ROOT / "backend" / "data" / "phase3" / "retrieval_audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print("\n=== FLAG SUMMARY ===", flush=True)
    for k, v in flags.items():
        print(f"  {k}: {len(v)} {v[:20]}{'...' if len(v) > 20 else ''}", flush=True)
    print(f"Wrote {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
