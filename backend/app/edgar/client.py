from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .. import db
from ..config import REQUEST_PAUSE_S, SEC_BASE, SEC_USER_AGENT, SEC_WWW, MAX_FILINGS

TICKERS_URL = f"{SEC_WWW}/files/company_tickers.json"
_last_request = 0.0


def _headers() -> dict[str, str]:
    return {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov",
    }


def _data_headers() -> dict[str, str]:
    return {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }


def _throttle() -> None:
    global _last_request
    elapsed = time.monotonic() - _last_request
    if elapsed < REQUEST_PAUSE_S:
        time.sleep(REQUEST_PAUSE_S - elapsed)
    _last_request = time.monotonic()


def fetch_json(url: str, headers: dict[str, str]) -> Any:
    _throttle()
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


def fetch_text(url: str) -> str:
    _throttle()
    host = "www.sec.gov" if "www.sec.gov" in url else "data.sec.gov"
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": host,
    }
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


def pad_cik(cik: str | int) -> str:
    return str(cik).lstrip("0") or "0"


def cik10(cik: str | int) -> str:
    return str(cik).zfill(10)


def load_tickers(force: bool = False) -> list[dict[str, Any]]:
    cached = None if force else db.meta_get("tickers")
    if cached:
        return json.loads(cached)
    raw = fetch_json(TICKERS_URL, _headers())
    rows = []
    for item in raw.values():
        rows.append(
            {
                "ticker": str(item["ticker"]).upper(),
                "cik": cik10(item["cik_str"]),
                "name": item["title"],
            }
        )
    db.meta_set("tickers", json.dumps(rows), datetime.now(timezone.utc).isoformat())
    return rows


def search_companies(query: str, limit: int = 12) -> list[dict[str, Any]]:
    from ..sp500 import refresh_sp500

    if db.sp500_count() < 400:
        refresh_sp500()
    q = query.strip().upper()
    rows = [dict(r) for r in db.list_sp500()]
    if not q:
        return rows[:limit]

    def haystack(row: dict[str, Any]) -> str:
        return " ".join(
            [
                row.get("ticker") or "",
                row.get("display") or "",
                row.get("name") or "",
                row.get("sector") or "",
            ]
        ).upper()

    exact = [r for r in rows if r["ticker"] == q or (r.get("display") or "") == q]
    prefix = [
        r
        for r in rows
        if r not in exact and ((r["ticker"] or "").startswith(q) or (r.get("display") or "").startswith(q))
    ]
    name_hits = [r for r in rows if r not in exact and r not in prefix and q in haystack(r)]
    return (exact + prefix + name_hits)[:limit]


def resolve_ticker(ticker: str) -> dict[str, Any]:
    from ..sp500 import refresh_sp500

    if db.sp500_count() < 400:
        refresh_sp500()
    t = ticker.strip().upper()
    sp = db.get_sp500(t)
    if sp is None:
        raise KeyError(f"{t} is not in the S&P 500")
    sec_ticker = sp["ticker"]
    cached = db.get_company(sec_ticker)
    if cached:
        return {"ticker": cached["ticker"], "cik": cached["cik"], "name": cached["name"]}
    rows = load_tickers()
    match = next((r for r in rows if r["ticker"] == sec_ticker), None)
    if not match:
        raise KeyError(f"Unknown ticker: {sec_ticker}")
    db.upsert_company(match["ticker"], match["cik"], match["name"])
    return match


def submissions_url(cik: str) -> str:
    return f"{SEC_BASE}/submissions/CIK{cik10(cik)}.json"


def companyfacts_url(cik: str) -> str:
    return f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik10(cik)}.json"


def filing_archive_url(cik: str, accession: str, primary_doc: str) -> str:
    accn = accession.replace("-", "")
    return f"{SEC_WWW}/Archives/edgar/data/{pad_cik(cik)}/{accn}/{primary_doc}"


def list_recent_filings(
    ticker: str, limit: int = MAX_FILINGS, force: bool = False
) -> list[dict[str, Any]]:
    company = resolve_ticker(ticker)
    if not force:
        cached = db.list_filings(company["ticker"])
        if cached:
            return [dict(row) for row in cached][:limit]
    data = fetch_json(submissions_url(company["cik"]), _data_headers())
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    rows: list[dict[str, Any]] = []
    for i, form in enumerate(forms):
        if form not in ("10-K", "10-Q"):
            continue
        accession = recent["accessionNumber"][i]
        primary_doc = recent.get("primaryDocument", [""])[i]
        filed = recent.get("filingDate", [""])[i]
        report_date = recent.get("reportDate", [""])[i]
        url = filing_archive_url(company["cik"], accession, primary_doc)
        rows.append(
            {
                "accession": accession,
                "ticker": company["ticker"],
                "cik": company["cik"],
                "form": form,
                "filed": filed,
                "report_date": report_date,
                "primary_doc": primary_doc,
                "filing_url": url,
            }
        )
        if len(rows) >= limit:
            break
    db.upsert_company(company["ticker"], company["cik"], data.get("name", company["name"]))
    db.upsert_filings(rows)
    return rows


def load_company_facts(cik: str, force: bool = False) -> dict[str, Any]:
    if not force:
        cached = db.get_facts_raw(cik10(cik))
        if cached:
            return json.loads(cached)
    payload = fetch_json(companyfacts_url(cik), _data_headers())
    encoded = json.dumps(payload)
    db.set_facts_raw(cik10(cik), encoded, datetime.now(timezone.utc).isoformat())
    return payload


def download_filing_html(filing: dict[str, Any] | Any) -> str:
    url = filing["filing_url"] if isinstance(filing, dict) else filing["filing_url"]
    return fetch_text(url)
