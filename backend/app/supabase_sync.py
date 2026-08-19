from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from . import db

_client = None


def _supabase():
    global _client
    if _client is not None:
        return _client
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    from supabase import create_client

    _client = create_client(url, key)
    return _client


def enabled() -> bool:
    return _supabase() is not None


def upsert_company(row: dict[str, Any]) -> None:
    client = _supabase()
    if client is None:
        return
    client.table("companies").upsert(
        {
            "ticker": row["ticker"],
            "display": row.get("display") or row["ticker"],
            "name": row["name"],
            "sector": row.get("sector"),
            "cik": row.get("cik"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="ticker",
    ).execute()


def upsert_filing(filing: dict[str, Any], analysis: Optional[dict[str, Any]] = None) -> None:
    client = _supabase()
    if client is None:
        return
    payload: dict[str, Any] = {
        "accession": filing["accession"],
        "ticker": filing["ticker"],
        "form": filing["form"],
        "filed": filing.get("filed"),
        "report_date": filing.get("report_date"),
        "filing_url": filing.get("filing_url"),
    }
    if analysis:
        sent = analysis.get("sentiment") or {}
        payload.update(
            {
                "sentiment_score": sent.get("score"),
                "positive_share": sent.get("positive_share"),
                "negative_share": sent.get("negative_share"),
                "neutral_share": sent.get("neutral_share"),
                "sentence_count": sent.get("sentence_count"),
                "metrics": analysis.get("metrics"),
                "agreement": analysis.get("agreement"),
                "sentences": analysis.get("sentences"),
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    client.table("filings").upsert(payload, on_conflict="accession").execute()


def set_preload_status(status: dict[str, Any]) -> None:
    client = _supabase()
    if client is None:
        return
    client.table("preload_status").upsert(
        {
            "id": 1,
            "running": bool(status.get("running")),
            "stage": status.get("stage"),
            "current": status.get("current"),
            "message": status.get("message"),
            "coverage": status.get("coverage"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="id",
    ).execute()


def push_all() -> dict[str, int]:
    client = _supabase()
    if client is None:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to sync.")

    companies = []
    for row in db.list_sp500():
        companies.append(
            {
                "ticker": row["ticker"],
                "display": row["display"] or row["ticker"],
                "name": row["name"],
                "sector": row["sector"],
                "cik": row["cik"],
            }
        )
    for i in range(0, len(companies), 200):
        client.table("companies").upsert(companies[i : i + 200], on_conflict="ticker").execute()

    filings = [dict(r) for r in db.list_all_filings()]
    pushed = 0
    for i in range(0, len(filings), 100):
        chunk = []
        for f in filings[i : i + 100]:
            analysis = db.get_analysis(f["accession"])
            item = {
                "accession": f["accession"],
                "ticker": f["ticker"],
                "form": f["form"],
                "filed": f["filed"],
                "report_date": f["report_date"],
                "filing_url": f["filing_url"],
            }
            if analysis:
                parsed = db.analysis_to_dict(analysis)
                sent = parsed["sentiment"]
                item.update(
                    {
                        "sentiment_score": sent["score"],
                        "positive_share": sent["positive_share"],
                        "negative_share": sent["negative_share"],
                        "neutral_share": sent["neutral_share"],
                        "sentence_count": sent["sentence_count"],
                        "metrics": parsed["metrics"],
                        "agreement": parsed["agreement"],
                        "sentences": parsed["sentences"],
                        "analyzed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            chunk.append(item)
        client.table("filings").upsert(chunk, on_conflict="accession").execute()
        pushed += len(chunk)

    set_preload_status(
        {
            "running": True,
            "stage": "sync",
            "message": "Cached filings synced to Supabase",
            "coverage": db.coverage(),
        }
    )
    return {"companies": len(companies), "filings": pushed}
