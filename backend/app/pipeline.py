from __future__ import annotations

import json
from typing import Any

from . import db
from .compare.metrics import agreement, summarize
from .config import MAX_FILINGS
from .edgar.client import list_recent_filings, load_company_facts, resolve_ticker
from .edgar.facts import metrics_for_filing
from .extract.mda import extract_mda
from .nlp.finbert import analyze_text


def _filing_dict(row: Any) -> dict[str, Any]:
    return {
        "accession": row["accession"],
        "ticker": row["ticker"],
        "cik": row["cik"],
        "form": row["form"],
        "filed": row["filed"],
        "report_date": row["report_date"],
        "primary_doc": row["primary_doc"],
        "filing_url": row["filing_url"],
    }


def company_overview(ticker: str, refresh: bool = False) -> dict[str, Any]:
    company = resolve_ticker(ticker)
    filings = list_recent_filings(company["ticker"], MAX_FILINGS, force=refresh)
    payload = []
    for f in filings:
        item = dict(f)
        analysis = db.get_analysis(f["accession"])
        if analysis:
            parsed = db.analysis_to_dict(analysis)
            item["sentiment"] = parsed["sentiment"]
            item["metrics"] = parsed["metrics"]
            item["agreement"] = parsed["agreement"]
            item["analyzed"] = True
        else:
            item["sentiment"] = None
            item["metrics"] = None
            item["agreement"] = None
            item["analyzed"] = False
        payload.append(item)
    summary = summarize(payload)
    return {"company": company, "filings": payload, **summary}


def analyze_filing(accession: str, force: bool = False) -> dict[str, Any]:
    filing_row = db.get_filing(accession)
    if filing_row is None:
        raise KeyError(f"Unknown filing {accession}. Load the company first.")
    filing = _filing_dict(filing_row)
    if not force:
        cached = db.get_analysis(accession)
        if cached:
            parsed = db.analysis_to_dict(cached)
            return {**filing, **parsed, "analyzed": True}

    text, source = extract_mda(filing, force=force)
    sentiment = analyze_text(text)
    facts = load_company_facts(filing["cik"])
    metrics = metrics_for_filing(facts, accession, filing["form"])
    agr_income = agreement(sentiment["score"], (metrics.get("net_income") or {}).get("pct_change"))
    agr_rev = agreement(sentiment["score"], (metrics.get("revenue") or {}).get("pct_change"))
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
        "mda_source": source,
        "sentiment": {
            "score": sentiment["score"],
            "positive_share": sentiment["positive_share"],
            "negative_share": sentiment["negative_share"],
            "neutral_share": sentiment["neutral_share"],
            "sentence_count": sentiment["sentence_count"],
        },
        "metrics": metrics,
        "agreement": {"net_income": agr_income, "revenue": agr_rev},
        "sentences": sentiment["sentences"],
        "analyzed": True,
    }
    try:
        from .supabase_sync import upsert_filing

        upsert_filing(filing, result)
    except Exception:
        pass
    return result


def filing_detail(accession: str) -> dict[str, Any]:
    filing_row = db.get_filing(accession)
    if filing_row is None:
        raise KeyError(f"Unknown filing {accession}")
    filing = _filing_dict(filing_row)
    cached = db.get_analysis(accession)
    mda = db.get_mda(accession)
    if cached is None:
        return {
            **filing,
            "analyzed": False,
            "sentiment": None,
            "metrics": None,
            "agreement": None,
            "sentences": [],
            "mda_source": None if mda is None else mda["source"],
        }
    parsed = db.analysis_to_dict(cached)
    return {
        **filing,
        **parsed,
        "analyzed": True,
        "mda_source": None if mda is None else mda["source"],
    }
