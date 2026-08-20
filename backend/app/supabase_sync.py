from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from . import db
from .compare.rollup import (
    build_company_stats,
    build_sector_stats,
    example_filing_payload,
    latest_analyzed_accession,
    pick_featured_tickers,
)

_client = None

# Keys published to live Supabase until Phase 3 adopts Phase 2 rankings.
_COMPANY_SYNC_KEYS = {
    "ticker",
    "display",
    "name",
    "sector",
    "cik",
    "n_filings",
    "mean_sentiment",
    "r_income",
    "p_income",
    "n_income",
    "r_revenue",
    "p_revenue",
    "n_revenue",
    "agreement_income",
    "agreement_revenue",
    "points",
    "featured",
    "updated_at",
}
_SECTOR_SYNC_KEYS = {
    "sector",
    "n_companies",
    "n_filings",
    "mean_sentiment",
    "r_income",
    "p_income",
    "n_income",
    "r_revenue",
    "p_revenue",
    "n_revenue",
    "agreement_income",
    "agreement_revenue",
    "points",
    "updated_at",
}


def _production_company_row(row: dict[str, Any]) -> dict[str, Any]:
    """Legacy production fields only — does not publish Phase 2 rankings yet."""
    out = {k: row[k] for k in _COMPANY_SYNC_KEYS if k in row}
    # Compact points: drop optional levels that bloat free-tier JSON
    slim_points = []
    for p in out.get("points") or []:
        slim_points.append(
            {
                "accession": p.get("accession"),
                "form": p.get("form"),
                "filed": p.get("filed"),
                "sentiment": p.get("sentiment"),
                "income_pct": p.get("income_pct"),
                "revenue_pct": p.get("revenue_pct"),
            }
        )
    out["points"] = slim_points
    return out


def _production_sector_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in _SECTOR_SYNC_KEYS if k in row}


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


def _score_risk_for_filing(accession: str) -> Optional[dict[str, Any]]:
    """Cheap bias demo: score Item 1A only when we need an example filing."""
    filing_row = db.get_filing(accession)
    if filing_row is None:
        return None
    filing = dict(filing_row)
    if not str(filing.get("form", "")).startswith("10-K"):
        # Prefer a 10-K for the same ticker when available
        for row in db.list_filings(filing["ticker"]):
            if str(row["form"]).startswith("10-K") and db.get_analysis(row["accession"]):
                filing = dict(row)
                accession = filing["accession"]
                break
        else:
            return None
    try:
        from .extract.risk import extract_risk_factors
        from .nlp.finbert import analyze_text

        text, _source = extract_risk_factors(filing)
        return analyze_text(text)
    except Exception:
        return None


def _upsert_chunks(client: Any, table: str, rows: list[dict[str, Any]], size: int = 100) -> int:
    if not rows:
        return 0
    for i in range(0, len(rows), size):
        client.table(table).upsert(rows[i : i + size]).execute()
    return len(rows)


def push_all(*, score_risk: bool = True) -> dict[str, int]:
    """Publish slim aggregates + a few example filings. Never dump full S&P sentence JSON."""
    client = _supabase()
    if client is None:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to sync.")

    set_preload_status(
        {
            "running": True,
            "stage": "rollup",
            "message": "Building industry / company aggregates",
            "coverage": db.coverage(),
        }
    )

    companies = build_company_stats()
    roles = pick_featured_tickers(companies)
    for c in companies:
        c["featured"] = c["ticker"] in roles
        c["updated_at"] = datetime.now(timezone.utc).isoformat()

    sectors = build_sector_stats(companies)
    for s in sectors:
        s["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Phase 2 must not replace production ranking fields yet. Sync only the
    # legacy-shaped columns the live UI already reads (strip additive keys).
    sync_companies = [_production_company_row(c) for c in companies]
    sync_sectors = [_production_sector_row(s) for s in sectors]

    n_companies = _upsert_chunks(client, "company_stats", sync_companies)
    n_sectors = _upsert_chunks(client, "sector_stats", sync_sectors)

    examples: list[dict[str, Any]] = []
    for ticker, role in roles.items():
        want_risk = score_risk and role in ("bias_demo", "highest_r", "lowest_r", "typical")
        accession = latest_analyzed_accession(ticker, prefer_10k=want_risk)
        if not accession:
            continue
        risk = None
        if want_risk:
            set_preload_status(
                {
                    "running": True,
                    "stage": "bias_demo",
                    "current": ticker,
                    "message": f"Scoring Item 1A bias demo for {ticker}",
                    "coverage": db.coverage(),
                }
            )
            risk = _score_risk_for_filing(accession)
        try:
            examples.append(example_filing_payload(accession, role, risk=risk))
        except KeyError:
            continue

    for ex in examples:
        ex["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        ex["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Replace example set so old heavy rows do not linger
    client.table("example_filings").delete().not("accession", "is", null).execute()
    n_examples = _upsert_chunks(client, "example_filings", examples, size=20) if examples else 0

    set_preload_status(
        {
            "running": False,
            "stage": "done",
            "message": (
                f"Synced {n_sectors} sectors, {n_companies} companies, "
                f"{n_examples} example filings"
            ),
            "coverage": db.coverage(),
        }
    )
    return {
        "sectors": n_sectors,
        "companies": n_companies,
        "example_filings": n_examples,
    }


# Back-compat no-ops: pipeline used to upsert every filing; industry-first path does not.
def upsert_company(_row: dict[str, Any]) -> None:
    return None


def upsert_filing(_filing: dict[str, Any], _analysis: Optional[dict[str, Any]] = None) -> None:
    return None
