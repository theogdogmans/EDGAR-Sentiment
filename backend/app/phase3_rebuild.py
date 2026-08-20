"""Phase 3 clean rebuild: Phase 1 extraction/XBRL + quality log + Phase 2 stats.

Uses the dedicated ``edgar_phase3.db`` (via ``app.config.DB_PATH``).
Does NOT publish to production Supabase.
"""

from __future__ import annotations

import json
import re
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from . import db
from .compare.rollup import (
    build_company_stats,
    build_sector_stats,
    ranking_eligibility_counts,
)
from .config import (
    EXTREME_NI_YOY,
    MAX_FILINGS,
    MDA_LONG_CHARS,
    MDA_SHORT_CHARS,
)
from .edgar.client import list_recent_filings, load_company_facts, resolve_ticker
from .edgar.facts import NON_COMPARABLE_REVENUE_SECTORS
from .pipeline import analyze_filing
from .sp500 import refresh_sp500, sp500_tickers


ITEM_7A_BODY = re.compile(
    r"item\s*7a[\.\s].{0,80}quantitative.{0,40}market\s+risk",
    re.I | re.S,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _flags_for_result(
    filing: dict[str, Any],
    *,
    mda_meta: Optional[dict[str, Any]],
    mda_text: Optional[str],
    metrics: Optional[dict[str, Any]],
    quality_rows_so_far: list[dict[str, Any]],
) -> list[str]:
    flags: list[str] = []
    form = str(filing.get("form") or "")
    chars = len(mda_text or "")
    if mda_meta is None or not (mda_text or "").strip():
        flags.append("extraction_failed")
    else:
        if chars < MDA_SHORT_CHARS:
            flags.append("mda_extremely_short")
        if chars > MDA_LONG_CHARS:
            flags.append("mda_extremely_long")
        if not (mda_meta.get("end_heading") or "").strip():
            flags.append("missing_end_heading")
        if form.startswith("10-K") and mda_text and ITEM_7A_BODY.search(mda_text):
            flags.append("item_7a_detected_in_10k_mda_body")

    metrics = metrics or {}
    ni = metrics.get("net_income") or {}
    rev = metrics.get("revenue") or {}
    if ni.get("status") == "ok":
        dur = ni.get("duration_days")
        if form.startswith("10-Q") and dur is not None and not (70 <= dur <= 100):
            flags.append("10q_duration_out_of_band")
        if form.startswith("10-K") and dur is not None and not (330 <= dur <= 400):
            flags.append("10k_duration_out_of_band")
        if ni.get("fp") and ni.get("prior_fp") and str(ni["fp"]) != str(ni["prior_fp"]):
            flags.append("mismatched_fp")
        yoy = ni.get("pct_change")
        if yoy is not None and abs(float(yoy)) >= EXTREME_NI_YOY:
            flags.append("extreme_net_income_yoy")
    if rev.get("status") == "ok":
        dur = rev.get("duration_days")
        if form.startswith("10-Q") and dur is not None and not (70 <= dur <= 100):
            flags.append("10q_revenue_duration_out_of_band")
        if form.startswith("10-K") and dur is not None and not (330 <= dur <= 400):
            flags.append("10k_revenue_duration_out_of_band")

    # Duplicates among attempts for this ticker
    acc = filing.get("accession")
    key = (form, filing.get("report_date"))
    for prev in quality_rows_so_far:
        if prev.get("accession") == acc:
            flags.append("duplicate_accession")
        if (prev.get("form"), prev.get("report_date")) == key and key[1]:
            flags.append("duplicate_form_report_date")
    return list(dict.fromkeys(flags))


def _quality_row_from_analysis(
    filing: dict[str, Any],
    result: dict[str, Any],
    *,
    failure_reason: Optional[str],
    flags: list[str],
) -> dict[str, Any]:
    mda_meta = result.get("mda_meta") or {}
    metrics = result.get("metrics") or {}
    sent = result.get("sentiment") or {}
    rev = metrics.get("revenue") or {}
    ni = metrics.get("net_income") or {}
    extraction_ok = 1 if (result.get("sentiment") and (mda_meta.get("char_count") or 0) > 0) else 0
    return {
        "ticker": filing["ticker"],
        "accession": filing["accession"],
        "form": filing.get("form"),
        "filed": filing.get("filed"),
        "report_date": filing.get("report_date"),
        "extraction_ok": extraction_ok,
        "extraction_source": mda_meta.get("source") or result.get("mda_source"),
        "mda_chars": mda_meta.get("char_count"),
        "start_heading": mda_meta.get("start_heading"),
        "end_heading": mda_meta.get("end_heading"),
        "extraction_status": mda_meta.get("status"),
        "extraction_confidence": mda_meta.get("confidence"),
        "sentence_count": sent.get("sentence_count"),
        "sentiment_score": sent.get("score"),
        "revenue_status": rev.get("status"),
        "revenue_tag": rev.get("tag"),
        "revenue_duration": rev.get("duration_days"),
        "revenue_yoy": rev.get("pct_change"),
        "ni_status": ni.get("status"),
        "ni_tag": ni.get("tag"),
        "ni_duration": ni.get("duration_days"),
        "ni_yoy": ni.get("pct_change"),
        "failure_reason": failure_reason
        or (None if extraction_ok else "extraction_or_sentiment_failed")
        or (rev.get("reason") if rev.get("status") != "ok" and ni.get("status") != "ok" else None),
        "flags_json": json.dumps(flags),
        "created_at": _now(),
    }


def analyze_filing_with_log(
    accession: str,
    *,
    force: bool = True,
    prior_logs: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    filing_row = db.get_filing(accession)
    if filing_row is None:
        raise KeyError(accession)
    filing = dict(filing_row)
    prior_logs = prior_logs or []
    failure_reason: Optional[str] = None
    result: dict[str, Any] = {}
    try:
        result = analyze_filing(accession, force=force)
        mda_row = db.get_mda(accession)
        mda_text = None if mda_row is None else mda_row["text"]
        mda_meta = result.get("mda_meta") or {}
        if mda_row is not None and not mda_meta.get("char_count"):
            mda_meta = {
                "source": mda_row["source"],
                "char_count": len(mda_row["text"] or ""),
                "start_heading": mda_row["start_heading"],
                "end_heading": mda_row["end_heading"],
                "status": mda_row["status"],
                "confidence": mda_row["confidence"],
            }
            result["mda_meta"] = mda_meta
        # When analysis was served from cache, reload metrics/sentiment shape
        if result.get("sentiment") and not mda_meta.get("char_count") and mda_text:
            mda_meta["char_count"] = len(mda_text)
            result["mda_meta"] = mda_meta
        flags = _flags_for_result(
            filing,
            mda_meta=mda_meta,
            mda_text=mda_text,
            metrics=result.get("metrics"),
            quality_rows_so_far=prior_logs,
        )
    except Exception as exc:  # noqa: BLE001
        failure_reason = f"{type(exc).__name__}: {exc}"
        flags = ["analysis_exception"]
        result = {"mda_meta": {}, "sentiment": None, "metrics": {}}
        log = {
            "ticker": filing["ticker"],
            "accession": filing["accession"],
            "form": filing.get("form"),
            "filed": filing.get("filed"),
            "report_date": filing.get("report_date"),
            "extraction_ok": 0,
            "extraction_source": None,
            "mda_chars": None,
            "start_heading": None,
            "end_heading": None,
            "extraction_status": "error",
            "extraction_confidence": None,
            "sentence_count": None,
            "sentiment_score": None,
            "revenue_status": None,
            "revenue_tag": None,
            "revenue_duration": None,
            "revenue_yoy": None,
            "ni_status": None,
            "ni_tag": None,
            "ni_duration": None,
            "ni_yoy": None,
            "failure_reason": failure_reason[:2000],
            "flags_json": json.dumps(flags),
            "created_at": _now(),
        }
        db.upsert_quality_log(log)
        return {"ok": False, "log": log, "error": failure_reason}

    log = _quality_row_from_analysis(filing, result, failure_reason=failure_reason, flags=flags)
    rev = (result.get("metrics") or {}).get("revenue") or {}
    ni = (result.get("metrics") or {}).get("net_income") or {}
    reasons = []
    if rev.get("status") != "ok" and rev.get("reason"):
        reasons.append(f"rev:{rev['reason']}")
    if ni.get("status") != "ok" and ni.get("reason"):
        reasons.append(f"ni:{ni['reason']}")
    if reasons:
        log["failure_reason"] = "; ".join(reasons)
    db.upsert_quality_log(log)
    return {"ok": True, "log": log, "result": result}


def rebuild_company(
    ticker: str,
    *,
    limit: int = MAX_FILINGS,
    force_filings: bool = True,
    force_analyze: bool = True,
) -> dict[str, Any]:
    company = resolve_ticker(ticker)
    filings = list_recent_filings(ticker, limit=limit, force=force_filings)
    load_company_facts(company["cik"], force=False)
    logs: list[dict[str, Any]] = []
    errors: list[str] = []
    for filing in filings:
        out = analyze_filing_with_log(filing["accession"], force=force_analyze, prior_logs=logs)
        logs.append(out["log"])
        if not out.get("ok"):
            errors.append(out.get("error") or "unknown")
    return {
        "ticker": company["ticker"],
        "filings_attempted": len(filings),
        "scored": sum(1 for lg in logs if lg.get("sentiment_score") is not None),
        "ni_ok": sum(1 for lg in logs if lg.get("ni_status") == "ok"),
        "rev_ok": sum(1 for lg in logs if lg.get("revenue_status") == "ok"),
        "sector_rev_blocked": sum(
            1
            for lg in logs
            if lg.get("revenue_status") == "unavailable"
            and "sector_not_comparable" in str(lg.get("failure_reason") or "")
        ),
        "errors": errors,
        "logs": logs,
    }


def prioritized_tickers(extra: Optional[Iterable[str]] = None) -> list[str]:
    """Comparison companies first, then remaining S&P 500."""
    refresh_sp500()
    all_tickers = list(sp500_tickers())
    universe = set(all_tickers)
    priority = [
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
    ]
    if extra:
        priority = [t.upper() for t in extra] + priority
    ordered: list[str] = []
    seen: set[str] = set()
    for t in priority:
        if t in universe and t not in seen:
            ordered.append(t)
            seen.add(t)
    for t in all_tickers:
        if t not in seen:
            ordered.append(t)
            seen.add(t)
    return ordered


def recompute_phase2_local() -> dict[str, Any]:
    """Compute Phase 2 stats into local phase2_* tables; do not push to Supabase."""
    companies = build_company_stats()
    sectors = build_sector_stats(companies)
    ts = _now()
    db.save_phase2_company_stats(companies, ts)
    db.save_phase2_sector_stats(sectors, ts)
    return {
        "companies": len(companies),
        "sectors": len(sectors),
        "eligibility_10q_ni": ranking_eligibility_counts(companies, form="10-Q", metric="net_income"),
        "eligibility_combined_ni": ranking_eligibility_counts(
            companies, form="combined", metric="net_income"
        ),
        "computed_at": ts,
    }


def sector_revenue_block_stats() -> dict[str, Any]:
    rows = [dict(r) for r in db.list_quality_logs()]
    blocked = [r for r in rows if (r.get("revenue_status") == "unavailable")]
    # Prefer reason from failure_reason or reconstruct via sector
    by_reason: Counter[str] = Counter()
    fin_tickers: set[str] = set()
    for r in blocked:
        fr = r.get("failure_reason") or ""
        if "sector_not_comparable" in fr or "rev:sector_not_comparable_revenue" in fr:
            by_reason["sector_not_comparable_revenue"] += 1
            fin_tickers.add(r["ticker"])
        elif "rev:" in fr:
            by_reason[fr.split("rev:")[-1].split(";")[0]] += 1
        else:
            by_reason[r.get("revenue_status") or "unavailable"] += 1
    # Also count via SP500 sector join for filings with null revenue in those sectors
    for r in rows:
        sp = db.get_sp500(r["ticker"])
        if not sp:
            continue
        if sp["sector"] in NON_COMPARABLE_REVENUE_SECTORS and r.get("revenue_status") != "ok":
            fin_tickers.add(r["ticker"])
    return {
        "filings_revenue_unavailable": len(blocked),
        "reason_counts": dict(by_reason),
        "companies_touched_financials_real_estate": len(fin_tickers),
        "non_comparable_sectors": sorted(NON_COMPARABLE_REVENUE_SECTORS),
    }
