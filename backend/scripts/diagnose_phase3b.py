#!/usr/bin/env python3
"""Diagnose GOOGL stall risk and XOM filing retrieval (no FinBERT)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("PHASE3_DB_NAME", "edgar_phase3.db")

from app import db  # noqa: E402
from app.edgar.client import (  # noqa: E402
    _collect_10k_10q,
    cik10,
    fetch_json,
    load_tickers,
    resolve_ticker,
    submissions_url,
    _data_headers,
)
from app.sp500 import refresh_sp500  # noqa: E402


def diagnose_ticker(ticker: str) -> dict:
    t0 = time.monotonic()
    stages = []

    def stage(label: str, **extra):
        stages.append({"stage": label, "elapsed_s": round(time.monotonic() - t0, 3), **extra})
        print(f"  [{stages[-1]['elapsed_s']:7.3f}s] {label} {extra}", flush=True)

    refresh_sp500()
    stage("resolve_start")
    company = resolve_ticker(ticker)
    stage("resolve_done", cik=company["cik"], company_name=company.get("name"), sec_ticker=company["ticker"])

    url = submissions_url(company["cik"])
    stage("submissions_fetch_start", url=url)
    data = fetch_json(url, _data_headers())
    recent = data.get("filings", {}).get("recent", {}) or {}
    files = data.get("filings", {}).get("files", []) or []
    forms = recent.get("form", []) or []
    n_10kq_recent = sum(1 for f in forms if f in ("10-K", "10-Q"))
    stage(
        "submissions_fetch_done",
        recent_forms=len(forms),
        recent_10k_10q=n_10kq_recent,
        shards=len(files),
        shard_names=[f.get("name") for f in files[:5]],
    )

    stage("collect_start")
    rows = _collect_10k_10q(company, 20)
    by_form = {}
    for r in rows:
        by_form[r["form"]] = by_form.get(r["form"], 0) + 1
    stage(
        "collect_done",
        n=len(rows),
        by_form=by_form,
        accessions=[r["accession"] for r in rows[:5]],
        oldest=rows[-1]["filed"] if rows else None,
        newest=rows[0]["filed"] if rows else None,
    )

    # Inspect first shard structure if present
    shard_info = None
    if files:
        name = files[0].get("name")
        stage("shard0_fetch_start", name=name)
        try:
            shard = fetch_json(f"https://data.sec.gov/submissions/{name}", _data_headers())
            keys = list(shard.keys())[:20]
            # Some shards wrap under 'filings'
            if "form" in shard:
                sforms = shard.get("form") or []
            elif isinstance(shard.get("filings"), dict):
                sforms = (shard["filings"].get("recent") or {}).get("form") or shard["filings"].get("form") or []
            else:
                sforms = []
            shard_info = {
                "keys": keys,
                "n_forms": len(sforms) if isinstance(sforms, list) else None,
                "n_10k_10q": sum(1 for f in sforms if f in ("10-K", "10-Q")) if isinstance(sforms, list) else None,
                "sample_top": type(shard).__name__,
            }
            stage("shard0_fetch_done", **shard_info)
        except Exception as exc:
            stage("shard0_fetch_error", error=str(exc))

    # Local DB state
    cached = [dict(r) for r in db.list_filings(company["ticker"])]
    ql = [dict(r) for r in db.list_quality_logs() if r["ticker"] == company["ticker"]]
    stage(
        "local_db",
        cached_filings=len(cached),
        quality_logs=len(ql),
        scored=sum(1 for r in ql if r.get("sentiment_score") is not None),
    )

    return {
        "ticker": ticker,
        "company": company,
        "stages": stages,
        "rows": rows,
        "by_form": by_form,
        "shard_info": shard_info,
        "files_meta": files,
    }


def duplicate_ciks() -> list[dict]:
    refresh_sp500()
    rows = load_tickers()
    by_t = {r["ticker"]: r for r in rows}
    sp = [dict(r) for r in db.list_sp500()]
    # map each display/ticker to cik
    mapped = []
    for r in sp:
        sec = by_t.get(r["ticker"])
        cik = sec["cik"] if sec else None
        if cik is None:
            # try companies table
            c = db.get_company(r["ticker"])
            cik = c["cik"] if c else None
        mapped.append({**r, "cik": cik})
    from collections import defaultdict

    by_cik = defaultdict(list)
    for m in mapped:
        if m.get("cik"):
            by_cik[m["cik"]].append(m)
    dups = []
    for cik, members in sorted(by_cik.items()):
        if len(members) > 1:
            dups.append(
                {
                    "cik": cik,
                    "tickers": [m["ticker"] for m in members],
                    "displays": [m.get("display") for m in members],
                    "names": [m.get("name") for m in members],
                }
            )
    return dups


def main() -> int:
    db.init_db()
    print("=== DUPLICATE CIKs IN S&P MAP ===", flush=True)
    dups = duplicate_ciks()
    print(json.dumps(dups, indent=2))

    out = {"duplicates": dups, "tickers": {}}
    for t in ("AAPL", "XOM", "GOOGL", "GOOG"):
        print(f"\n=== DIAGNOSE {t} ===", flush=True)
        try:
            out["tickers"][t] = diagnose_ticker(t)
        except Exception as exc:
            print(f"FAILED {t}: {exc}", flush=True)
            out["tickers"][t] = {"error": str(exc)}

    path = ROOT / "backend" / "data" / "phase3" / "diagnose_3b.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # shrink rows for dump
    slim = {"duplicates": dups, "tickers": {}}
    for t, payload in out["tickers"].items():
        if "error" in payload:
            slim["tickers"][t] = payload
            continue
        slim["tickers"][t] = {
            "company": payload["company"],
            "by_form": payload["by_form"],
            "n_rows": len(payload["rows"]),
            "stages": payload["stages"],
            "shard_info": payload["shard_info"],
            "n_shards": len(payload.get("files_meta") or []),
        }
    path.write_text(json.dumps(slim, indent=2))
    print(f"\nWrote {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
