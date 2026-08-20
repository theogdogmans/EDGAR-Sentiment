"""Phase 3 clean rebuild: Phase 1 extraction/XBRL + quality log + Phase 2 stats.

Uses the dedicated ``edgar_phase3.db`` (via ``app.config.DB_PATH``).
Does NOT publish to production Supabase.

Phase 3B additions:
- Per-filing stage instrumentation
- Bounded HTTP / filing retries and soft timeouts
- Filing-level checkpoint statuses (``filing_jobs``)
- Registrant-level CIK dedupe (share classes processed once)
"""

from __future__ import annotations

import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from . import db
from .compare.metrics import agreement
from .compare.rollup import (
    build_company_stats,
    build_sector_stats,
    ranking_eligibility_counts,
)
from .config import (
    EXTREME_NI_YOY,
    FILING_MAX_ATTEMPTS,
    FILING_SOFT_TIMEOUT_S,
    MAX_FILINGS,
    MDA_LONG_CHARS,
    MDA_SHORT_CHARS,
)
from .edgar.client import (
    download_filing_html,
    list_recent_filings,
    load_company_facts,
    resolve_ticker,
)
from .edgar.facts import NON_COMPARABLE_REVENUE_SECTORS, metrics_for_filing
from .extract.mda import extract_mda
from .filing_trace import FilingTrace
from .nlp.finbert import analyze_text
from .registrants import registrant_plan
from .sp500 import refresh_sp500, sp500_tickers


ITEM_7A_BODY = re.compile(
    r"item\s*7a[\.\s].{0,80}quantitative.{0,40}market\s+risk",
    re.I | re.S,
)

TRANSIENT_MARKERS = (
    "Timeout",
    "timeout",
    "timed out",
    "ConnectError",
    "ReadTimeout",
    "WriteTimeout",
    "NetworkError",
    "RemoteProtocolError",
    "503",
    "502",
    "429",
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


def _is_transient(exc: BaseException | str) -> bool:
    msg = str(exc)
    return any(m in msg for m in TRANSIENT_MARKERS)


def _write_job(
    filing: dict[str, Any],
    *,
    status: str,
    stage: str,
    attempts: int,
    last_error: Optional[str],
    elapsed_s: float,
) -> None:
    db.upsert_filing_job(
        {
            "accession": filing["accession"],
            "ticker": filing["ticker"],
            "cik": filing["cik"],
            "form": filing.get("form"),
            "status": status,
            "stage": stage,
            "attempts": attempts,
            "last_error": None if last_error is None else last_error[:2000],
            "elapsed_s": elapsed_s,
            "updated_at": _now(),
        }
    )


def _failure_log(filing: dict[str, Any], reason: str, flags: list[str]) -> dict[str, Any]:
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
        "failure_reason": reason[:2000],
        "flags_json": json.dumps(flags),
        "created_at": _now(),
    }
    db.upsert_quality_log(log)
    return log


def filing_already_complete(accession: str) -> bool:
    """True if FinBERT already succeeded for this accession (never redo)."""
    job = db.get_filing_job(accession)
    if job is not None and job["status"] == db.JOB_COMPLETE:
        return True
    if db.analysis_complete(accession):
        return True
    return False


def analyze_filing_with_log(
    accession: str,
    *,
    force: bool = False,
    prior_logs: Optional[list[dict[str, Any]]] = None,
    skip_completed: bool = True,
) -> dict[str, Any]:
    """Analyze one filing with stage logs, soft timeout, and job status updates.

    Failures are recorded in ``quality_log`` / ``filing_jobs`` and returned —
    they do not raise (caller continues to next filing).
    """
    filing_row = db.get_filing(accession)
    if filing_row is None:
        raise KeyError(accession)
    filing = dict(filing_row)
    prior_logs = prior_logs or []

    job = db.get_filing_job(accession)
    attempts = int(job["attempts"]) if job is not None else 0
    if job is not None and job["status"] == db.JOB_FAILED_FINAL:
        return {
            "ok": False,
            "skipped": True,
            "log": _failure_log(
                filing, f"already_failed_final: {job['last_error']}", ["failed_final"]
            ),
            "error": job["last_error"],
        }

    if skip_completed and not force and filing_already_complete(accession):
        _write_job(
            filing,
            status=db.JOB_COMPLETE,
            stage="skip_completed",
            attempts=attempts,
            last_error=None,
            elapsed_s=0.0,
        )
        cached = db.get_analysis(accession)
        mda_row = db.get_mda(accession)
        result: dict[str, Any] = {"mda_meta": {}, "sentiment": None, "metrics": {}}
        if cached is not None:
            parsed = db.analysis_to_dict(cached)
            result.update(parsed)
            if mda_row is not None:
                result["mda_meta"] = {
                    "source": mda_row["source"],
                    "char_count": len(mda_row["text"] or ""),
                    "start_heading": mda_row["start_heading"],
                    "end_heading": mda_row["end_heading"],
                    "status": mda_row["status"],
                    "confidence": mda_row["confidence"],
                }
            flags = _flags_for_result(
                filing,
                mda_meta=result.get("mda_meta"),
                mda_text=None if mda_row is None else mda_row["text"],
                metrics=result.get("metrics"),
                quality_rows_so_far=prior_logs,
            )
            log = _quality_row_from_analysis(filing, result, failure_reason=None, flags=flags)
            db.upsert_quality_log(log)
            return {"ok": True, "skipped": True, "log": log, "result": result}
        return {
            "ok": True,
            "skipped": True,
            "log": {
                "ticker": filing["ticker"],
                "accession": accession,
                "sentiment_score": None,
                "ni_status": None,
                "revenue_status": None,
            },
        }

    trace = FilingTrace(
        ticker=filing["ticker"],
        cik=filing["cik"],
        accession=accession,
        form=str(filing.get("form") or ""),
    )
    attempts += 1
    _write_job(
        filing,
        status=db.JOB_PROCESSING,
        stage="start",
        attempts=attempts,
        last_error=None,
        elapsed_s=0.0,
    )
    trace.log("start", retry_status=f"attempt={attempts}")

    def _budget_ok(stage: str) -> None:
        if trace.elapsed() > FILING_SOFT_TIMEOUT_S:
            raise TimeoutError(
                f"soft_timeout after {trace.elapsed()}s at stage={stage} "
                f"(limit={FILING_SOFT_TIMEOUT_S}s)"
            )

    try:
        _budget_ok("sec_submissions")
        trace.log("sec_submissions", success=True)

        if not force:
            cached = db.get_analysis(accession)
            if cached is not None:
                parsed = db.analysis_to_dict(cached)
                mda_row = db.get_mda(accession)
                mda_meta: dict[str, Any] = {}
                mda_text = None
                if mda_row is not None:
                    mda_text = mda_row["text"]
                    mda_meta = {
                        "source": mda_row["source"],
                        "char_count": len(mda_text or ""),
                        "start_heading": mda_row["start_heading"],
                        "end_heading": mda_row["end_heading"],
                        "status": mda_row["status"],
                        "confidence": mda_row["confidence"],
                    }
                result = {**filing, **parsed, "mda_meta": mda_meta, "analyzed": True}
                flags = _flags_for_result(
                    filing,
                    mda_meta=mda_meta,
                    mda_text=mda_text,
                    metrics=result.get("metrics"),
                    quality_rows_so_far=prior_logs,
                )
                log = _quality_row_from_analysis(filing, result, failure_reason=None, flags=flags)
                db.upsert_quality_log(log)
                _write_job(
                    filing,
                    status=db.JOB_COMPLETE,
                    stage="cache_hit",
                    attempts=attempts,
                    last_error=None,
                    elapsed_s=trace.elapsed(),
                )
                trace.log("cache_hit", success=True)
                return {"ok": True, "log": log, "result": result}

        _budget_ok("filing_download")
        trace.log("filing_download", retry_status="start")
        if force or db.get_mda(accession) is None:
            download_filing_html(filing)
        trace.log("filing_download", success=True)

        _budget_ok("mda_extraction")
        trace.log("mda_extraction", retry_status="start")
        text, mda_meta = extract_mda(filing, force=force)
        trace.log(
            "mda_extraction",
            success=True,
            mda_chars=len(text or ""),
            source=mda_meta.get("source"),
        )

        _budget_ok("finbert_scoring")
        remaining = max(5.0, FILING_SOFT_TIMEOUT_S - trace.elapsed())
        trace.log("finbert_scoring", retry_status=f"budget_s={remaining:.0f}")

        def _score() -> dict[str, Any]:
            return analyze_text(text)

        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_score)
            try:
                sentiment = fut.result(timeout=remaining)
            except FuturesTimeout as exc:
                raise TimeoutError(
                    f"finbert_timeout after {trace.elapsed()}s (budget={remaining:.0f}s)"
                ) from exc
        trace.log("finbert_scoring", success=True, sentences=sentiment.get("sentence_count"))

        _budget_ok("companyfacts_retrieval")
        trace.log("companyfacts_retrieval", retry_status="start")
        facts = load_company_facts(filing["cik"], force=False)
        trace.log("companyfacts_retrieval", success=True)

        _budget_ok("xbrl_matching")
        trace.log("xbrl_matching", retry_status="start")
        sp = db.get_sp500(filing["ticker"])
        sector = sp["sector"] if sp else None
        metrics = metrics_for_filing(
            facts,
            accession,
            filing["form"],
            report_date=filing.get("report_date"),
            sector=sector,
        )
        trace.log(
            "xbrl_matching",
            success=True,
            ni=(metrics.get("net_income") or {}).get("status"),
            rev=(metrics.get("revenue") or {}).get("status"),
        )

        _budget_ok("database_write")
        trace.log("database_write", retry_status="start")
        ni_pct = (metrics.get("net_income") or {}).get("pct_change")
        rev_pct = (metrics.get("revenue") or {}).get("pct_change")
        agr_income = agreement(sentiment["score"], ni_pct)
        agr_rev = agreement(sentiment["score"], rev_pct)
        db.set_analysis(
            {
                "accession": accession,
                "sentiment_score": sentiment["score"],
                "positive_share": sentiment["positive_share"],
                "negative_share": sentiment["negative_share"],
                "neutral_share": sentiment["neutral_share"],
                "sentence_count": sentiment["sentence_count"],
                "sentences_json": json.dumps(sentiment["sentences"]),
                "metrics_json": json.dumps(metrics),
                "agreement_income": None if agr_income is None else int(agr_income),
                "agreement_revenue": None if agr_rev is None else int(agr_rev),
            }
        )
        result = {
            **filing,
            "mda_source": mda_meta.get("source"),
            "mda_meta": mda_meta,
            "sentiment": {
                "score": sentiment["score"],
                "positive_share": sentiment["positive_share"],
                "negative_share": sentiment["negative_share"],
                "neutral_share": sentiment["neutral_share"],
                "sentence_count": sentiment["sentence_count"],
            },
            "metrics": metrics,
            "agreement": {"net_income": agr_income, "revenue": agr_rev},
            "analyzed": True,
        }
        flags = _flags_for_result(
            filing,
            mda_meta=mda_meta,
            mda_text=text,
            metrics=metrics,
            quality_rows_so_far=prior_logs,
        )
        log = _quality_row_from_analysis(filing, result, failure_reason=None, flags=flags)
        rev = metrics.get("revenue") or {}
        ni = metrics.get("net_income") or {}
        reasons = []
        if rev.get("status") != "ok" and rev.get("reason"):
            reasons.append(f"rev:{rev['reason']}")
        if ni.get("status") != "ok" and ni.get("reason"):
            reasons.append(f"ni:{ni['reason']}")
        if reasons:
            log["failure_reason"] = "; ".join(reasons)
        db.upsert_quality_log(log)
        _write_job(
            filing,
            status=db.JOB_COMPLETE,
            stage="database_write",
            attempts=attempts,
            last_error=None,
            elapsed_s=trace.elapsed(),
        )
        trace.log("database_write", success=True)
        return {"ok": True, "log": log, "result": result}

    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
        stage = trace.stage
        transient = _is_transient(exc)
        final = (not transient) or attempts >= FILING_MAX_ATTEMPTS
        status = db.JOB_FAILED_FINAL if final else db.JOB_FAILED_RETRYABLE
        flags = ["analysis_exception", f"stage:{stage}"]
        if transient:
            flags.append("transient")
        if final:
            flags.append("failed_final")
        else:
            flags.append("failed_retryable")
        log = _failure_log(filing, f"stage={stage}; {err}", flags)
        _write_job(
            filing,
            status=status,
            stage=stage,
            attempts=attempts,
            last_error=err,
            elapsed_s=trace.elapsed(),
        )
        trace.log(stage, success=False, exception=err, retry_status=status)
        print(f"    FAIL {filing['ticker']} {accession} {err}", flush=True)
        return {"ok": False, "log": log, "error": err, "job_status": status}


def rebuild_company(
    ticker: str,
    *,
    limit: int = MAX_FILINGS,
    force_filings: bool = True,
    force_analyze: bool = False,
    skip_completed: bool = True,
) -> dict[str, Any]:
    """Process one ticker's filings. Filing failures do not abort the company."""
    try:
        company = resolve_ticker(ticker)
    except Exception as exc:  # noqa: BLE001
        reason = f"resolve_ticker: {type(exc).__name__}: {exc}"
        print(f"  COMPANY FAIL {ticker}: {reason}", flush=True)
        return {
            "ticker": ticker,
            "filings_attempted": 0,
            "scored": 0,
            "ni_ok": 0,
            "rev_ok": 0,
            "errors": [reason],
            "logs": [],
            "company_failed": True,
        }

    try:
        filings = list_recent_filings(ticker, limit=limit, force=force_filings)
        load_company_facts(company["cik"], force=False)
    except Exception as exc:  # noqa: BLE001
        reason = f"list_filings: {type(exc).__name__}: {exc}"
        print(f"  COMPANY FAIL {ticker}: {reason}", flush=True)
        return {
            "ticker": company["ticker"],
            "cik": company["cik"],
            "filings_attempted": 0,
            "scored": 0,
            "ni_ok": 0,
            "rev_ok": 0,
            "errors": [reason],
            "logs": [],
            "company_failed": True,
            "cik_resolution": company.get("cik_resolution"),
        }

    logs: list[dict[str, Any]] = []
    errors: list[str] = []
    for filing in filings:
        if db.get_filing_job(filing["accession"]) is None:
            _write_job(
                filing,
                status=db.JOB_PENDING,
                stage="queued",
                attempts=0,
                last_error=None,
                elapsed_s=0.0,
            )
        out = analyze_filing_with_log(
            filing["accession"],
            force=force_analyze,
            prior_logs=logs,
            skip_completed=skip_completed,
        )
        logs.append(out.get("log") or {})
        if not out.get("ok"):
            errors.append(out.get("error") or "unknown")
    return {
        "ticker": company["ticker"],
        "cik": company["cik"],
        "cik_resolution": company.get("cik_resolution"),
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
        "company_failed": False,
    }


def rebuild_registrant(
    item: dict[str, Any],
    *,
    limit: int = MAX_FILINGS,
    force_filings: bool = True,
    force_analyze: bool = False,
    skip_completed: bool = True,
) -> dict[str, Any]:
    """Process one SEC registrant (CIK) once under its canonical S&P ticker."""
    canon = item["canonical_ticker"]
    summary = rebuild_company(
        canon,
        limit=limit,
        force_filings=force_filings,
        force_analyze=force_analyze,
        skip_completed=skip_completed,
    )
    summary["alias_tickers"] = item.get("alias_tickers") or []
    summary["is_duplicate_share_class"] = bool(item.get("is_duplicate_share_class"))
    summary["member_tickers"] = item.get("member_tickers") or [canon]
    for alias in summary["alias_tickers"]:
        try:
            c = resolve_ticker(alias, validate_history=False)
            db.upsert_company(alias, summary.get("cik") or c["cik"], c.get("name") or alias)
        except Exception:
            if summary.get("cik"):
                db.upsert_company(alias, summary["cik"], alias)
    return summary


def order_registrants_for_rebuild(
    plan: list[dict[str, Any]],
    *,
    prefer_empty_first: bool = True,
) -> list[dict[str, Any]]:
    """Deterministic order: zero completed analyses first, then by ticker."""
    if not prefer_empty_first:
        return sorted(plan, key=lambda x: x["canonical_ticker"])

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        t = item["canonical_ticker"]
        n = db.count_completed_analyses_for_ticker(t)
        for m in item.get("member_tickers") or []:
            if m != t:
                n = max(n, db.count_completed_analyses_for_ticker(m))
        return (0 if n == 0 else 1, t)

    return sorted(plan, key=sort_key)


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
    plan = registrant_plan()
    alias_set = {a for item in plan for a in item.get("alias_tickers") or []}
    for row in companies:
        if row["ticker"] in alias_set:
            row["exclude_from_sector"] = True
            row["_alias_share_class"] = True
    # Sector pools use canonical registrants only (no double-count share classes).
    sector_input = [c for c in companies if not c.get("exclude_from_sector")]
    sectors = build_sector_stats(sector_input)
    ts = _now()
    db.save_phase2_company_stats(companies, ts)
    db.save_phase2_sector_stats(sectors, ts)
    return {
        "companies": len(companies),
        "sectors": len(sectors),
        "alias_excluded_from_sector": sorted(alias_set),
        "eligibility_10q_ni": ranking_eligibility_counts(companies, form="10-Q", metric="net_income"),
        "eligibility_combined_ni": ranking_eligibility_counts(
            companies, form="combined", metric="net_income"
        ),
        "computed_at": ts,
    }


def sector_revenue_block_stats() -> dict[str, Any]:
    rows = [dict(r) for r in db.list_quality_logs()]
    blocked = [r for r in rows if (r.get("revenue_status") == "unavailable")]
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
