"""Registrant-level (CIK) helpers for share-class / duplicate-ticker handling.

S&P 500 lists multiple share classes (GOOG/GOOGL, FOX/FOXA, NWS/NWSA) that
map to one SEC registrant. Rebuilds process each CIK once under a canonical
ticker; aliases remain in the universe for membership reporting but do not
re-score identical filings or double-count in sector pools.

CIK recovery (e.g. XOM Holdings → EXXON MOBIL CORP) happens in
``resolve_ticker(validate_history=True)`` at filing-collection time, not
during the fast ticker→CIK grouping used for dedupe planning.
"""

from __future__ import annotations

from typing import Any, Optional

from . import db
from .edgar.client import cik10, load_tickers, resolve_ticker
from .sp500 import PRIORITY, refresh_sp500


def _canonical_among(tickers: list[str]) -> str:
    """Prefer PRIORITY order, else lexicographic ticker."""
    pri = [t for t in PRIORITY if t in tickers]
    if pri:
        return pri[0]
    return sorted(tickers)[0]


def map_tickers_to_ciks(
    tickers: Optional[list[str]] = None,
    *,
    validate_history: bool = False,
) -> dict[str, str]:
    """ticker -> cik for S&P universe.

    Default is a fast ``company_tickers.json`` lookup (no per-ticker
    submissions probes). Set ``validate_history=True`` only when thin-CIK
    recovery is required for every row (slow).
    """
    if tickers is None:
        refresh_sp500()
        tickers = [r["ticker"] for r in db.list_sp500()]
    out: dict[str, str] = {}
    if validate_history:
        for t in tickers:
            try:
                company = resolve_ticker(t, validate_history=True)
                out[t] = cik10(company["cik"])
            except Exception:
                continue
        return out

    by_sec = {r["ticker"]: cik10(r["cik"]) for r in load_tickers()}
    for t in tickers:
        sp = db.get_sp500(t)
        key = sp["ticker"] if sp is not None else t.strip().upper()
        cik = by_sec.get(key)
        if cik:
            out[t.strip().upper() if sp is None else key] = cik
            # Also key by the requested symbol when it differs from SEC ticker
            out[t.strip().upper()] = cik
    return out


def duplicate_cik_groups(ticker_to_cik: Optional[dict[str, str]] = None) -> list[dict[str, Any]]:
    ticker_to_cik = ticker_to_cik or map_tickers_to_ciks()
    by_cik: dict[str, list[str]] = {}
    for t, cik in ticker_to_cik.items():
        by_cik.setdefault(cik, []).append(t)
    groups = []
    for cik, members in sorted(by_cik.items()):
        uniq = sorted(set(members))
        if len(uniq) < 2:
            continue
        canon = _canonical_among(uniq)
        groups.append(
            {
                "cik": cik,
                "tickers": uniq,
                "canonical_ticker": canon,
                "aliases": sorted(m for m in uniq if m != canon),
            }
        )
    return groups


def registrant_plan(tickers: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """Ordered unique-CIK work items for rebuild.

    Returns list of dicts:
      cik, canonical_ticker, alias_tickers, is_duplicate_share_class

    Note: ``cik`` here is the SEC company_tickers mapping. Actual rebuild
    calls ``resolve_ticker(..., validate_history=True)`` which may recover
    a different operating-company CIK (XOM case).
    """
    if tickers is None:
        refresh_sp500()
        from .sp500 import sp500_tickers

        tickers = sp500_tickers()
    elif db.sp500_count() < 1:
        refresh_sp500()
    ticker_to_cik = map_tickers_to_ciks(tickers, validate_history=False)
    by_cik: dict[str, list[str]] = {}
    for t in tickers:
        cik = ticker_to_cik.get(t) or ticker_to_cik.get(t.strip().upper())
        if not cik:
            continue
        by_cik.setdefault(cik, []).append(t)

    plan: list[dict[str, Any]] = []
    seen_cik: set[str] = set()
    for t in tickers:
        cik = ticker_to_cik.get(t) or ticker_to_cik.get(t.strip().upper())
        if not cik or cik in seen_cik:
            continue
        members = list(dict.fromkeys(by_cik[cik]))
        canon = _canonical_among(members)
        seen_cik.add(cik)
        plan.append(
            {
                "cik": cik,
                "canonical_ticker": canon,
                "alias_tickers": sorted(m for m in members if m != canon),
                "is_duplicate_share_class": len(members) > 1,
                "member_tickers": sorted(members),
            }
        )
    return plan


def is_alias_ticker(ticker: str, plan: Optional[list[dict[str, Any]]] = None) -> bool:
    plan = plan or registrant_plan()
    for item in plan:
        if ticker in item["alias_tickers"]:
            return True
    return False
