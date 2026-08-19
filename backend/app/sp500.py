from __future__ import annotations

import csv
from io import StringIO
from typing import Any

import httpx

from . import db
from .config import SEC_USER_AGENT, SP500_CSV_URLS
from .edgar.client import load_tickers

PRIORITY = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "GOOG",
    "META",
    "BRK-B",
    "AVGO",
    "JPM",
    "XOM",
    "UNH",
    "LLY",
    "V",
    "JNJ",
)


def _sec_candidates(symbol: str) -> list[str]:
    s = symbol.strip().upper()
    return list(dict.fromkeys([s, s.replace(".", "-"), s.replace("-", ".")]))


def _download_csv() -> str:
    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "text/csv,*/*"}
    last_error: Exception | None = None
    with httpx.Client(timeout=45.0, follow_redirects=True) as client:
        for url in SP500_CSV_URLS:
            try:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                if "Symbol" in resp.text or "symbol" in resp.text:
                    return resp.text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
    raise RuntimeError(f"Could not download S&P 500 list: {last_error}")


def refresh_sp500(force: bool = False) -> list[dict[str, Any]]:
    if not force and db.sp500_count() >= 400:
        return [dict(row) for row in db.list_sp500()]

    raw = _download_csv()
    reader = csv.DictReader(StringIO(raw))
    sec_rows = load_tickers()
    by_ticker = {row["ticker"]: row for row in sec_rows}

    mapped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in reader:
        symbol = (item.get("Symbol") or item.get("symbol") or "").strip()
        name = (item.get("Name") or item.get("Security") or item.get("name") or symbol).strip()
        sector = (item.get("Sector") or item.get("GICS Sector") or "").strip()
        if not symbol:
            continue
        match = None
        for candidate in _sec_candidates(symbol):
            if candidate in by_ticker:
                match = by_ticker[candidate]
                break
        if match is None or match["ticker"] in seen:
            continue
        seen.add(match["ticker"])
        mapped.append(
            {
                "ticker": match["ticker"],
                "display": symbol.upper(),
                "name": name or match["name"],
                "sector": sector,
            }
        )
    if len(mapped) < 400:
        raise RuntimeError(f"S&P 500 map only found {len(mapped)} SEC tickers")
    db.replace_sp500(mapped)
    return mapped


def sp500_tickers() -> list[str]:
    if db.sp500_count() < 400:
        refresh_sp500()
    rows = [dict(r) for r in db.list_sp500()]
    tickers = [r["ticker"] for r in rows]
    head = [t for t in PRIORITY if t in tickers]
    rest = [t for t in tickers if t not in head]
    return head + rest
