from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .. import db
from ..config import (
    HTTP_DOWNLOAD_TIMEOUT_S,
    HTTP_MAX_RETRIES,
    HTTP_TIMEOUT_S,
    MAX_FILINGS,
    MIN_CIK_HISTORY,
    REQUEST_PAUSE_S,
    SEC_BASE,
    SEC_USER_AGENT,
    SEC_WWW,
)

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


def fetch_json(url: str, headers: dict[str, str], *, timeout: Optional[float] = None) -> Any:
    """GET JSON with bounded retries. Never retries forever."""
    timeout = HTTP_TIMEOUT_S if timeout is None else timeout
    last_exc: Exception | None = None
    for attempt in range(HTTP_MAX_RETRIES + 1):
        _throttle()
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= HTTP_MAX_RETRIES:
                break
            time.sleep(0.5 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def fetch_text(url: str, *, timeout: Optional[float] = None) -> str:
    timeout = HTTP_DOWNLOAD_TIMEOUT_S if timeout is None else timeout
    last_exc: Exception | None = None
    host = "www.sec.gov" if "www.sec.gov" in url else "data.sec.gov"
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": host,
    }
    for attempt in range(HTTP_MAX_RETRIES + 1):
        _throttle()
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.text
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= HTTP_MAX_RETRIES:
                break
            time.sleep(0.5 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def pad_cik(cik: str | int) -> str:
    return str(cik).lstrip("0") or "0"


def cik10(cik: str | int) -> str:
    return str(cik).zfill(10)


def accession_cik_prefix(accession: str) -> str:
    """CIK embedded in accession ``##########-YY-######``."""
    head = str(accession).split("-")[0]
    return cik10(head)


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


def submissions_url(cik: str) -> str:
    return f"{SEC_BASE}/submissions/CIK{cik10(cik)}.json"


def companyfacts_url(cik: str) -> str:
    return f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik10(cik)}.json"


def filing_archive_url(cik: str, accession: str, primary_doc: str) -> str:
    accn = accession.replace("-", "")
    return f"{SEC_WWW}/Archives/edgar/data/{pad_cik(cik)}/{accn}/{primary_doc}"


def count_10k_10q_in_submissions(data: dict[str, Any]) -> int:
    recent = (data.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    n = sum(1 for f in forms if f in ("10-K", "10-Q"))
    # Shards imply additional history; treat each shard filingCount as soft signal
    files = (data.get("filings") or {}).get("files") or []
    if files and n < MIN_CIK_HISTORY:
        # Don't double-count; just note shards exist — actual count via collect
        return n  # caller may still probe shards via collect
    return n


def probe_eligible_filing_count(cik: str, limit: int = MAX_FILINGS) -> int:
    """How many distinct 10-K/10-Q we can collect up to ``limit``."""
    rows = collect_10k_10q_for_cik(cik, ticker="PROBE", limit=limit)
    return len(rows)


def resolve_ticker(ticker: str, *, validate_history: bool = True) -> dict[str, Any]:
    """Map S&P ticker → SEC company, with history validation for stale ticker grabs.

    Example failure mode: ``XOM`` in company_tickers.json briefly points at a new
    Holdings shell (few filings) while operating-company 10-K/10-Q remain under
    the historic CIK embedded in accession prefixes.
    """
    from ..sp500 import refresh_sp500

    t = ticker.strip().upper()
    sp = db.get_sp500(t)
    if sp is None:
        refresh_sp500()
        sp = db.get_sp500(t)
    if sp is None:
        raise KeyError(f"{t} is not in the S&P 500")
    sec_ticker = sp["ticker"]

    cached = db.get_company(sec_ticker)
    if cached and not validate_history:
        return {"ticker": cached["ticker"], "cik": cached["cik"], "name": cached["name"]}

    rows = load_tickers()
    match = next((r for r in rows if r["ticker"] == sec_ticker), None)
    if not match:
        raise KeyError(f"Unknown ticker: {sec_ticker}")

    company = {
        "ticker": match["ticker"],
        "cik": match["cik"],
        "name": match["name"],
        "cik_resolution": "company_tickers",
    }

    if validate_history:
        company = _prefer_cik_with_history(company)

    db.upsert_company(company["ticker"], company["cik"], company["name"])
    return company


def _prefer_cik_with_history(company: dict[str, Any]) -> dict[str, Any]:
    """If mapped CIK has thin 10-K/10-Q history, recover via accession CIK prefix."""
    cik = cik10(company["cik"])
    try:
        data = fetch_json(submissions_url(cik), _data_headers())
    except Exception:
        return company

    company = {
        **company,
        "name": data.get("name") or company.get("name") or company["ticker"],
    }
    n_recent = count_10k_10q_in_submissions(data)
    files = (data.get("filings") or {}).get("files") or []
    if n_recent >= MIN_CIK_HISTORY or files:
        # Enough in recent OR shards exist to fill history
        if n_recent >= MIN_CIK_HISTORY:
            return company
        # Probe full collect before abandoning mapped CIK
        n_collect = len(collect_10k_10q_for_cik(cik, ticker=company["ticker"], limit=MAX_FILINGS))
        if n_collect >= MIN_CIK_HISTORY:
            return company

    # Thin history: try accession prefixes from whatever filings exist
    recent = (data.get("filings") or {}).get("recent") or {}
    accessions = recent.get("accessionNumber") or []
    forms = recent.get("form") or []
    candidate_ciks: list[str] = []
    for i, acc in enumerate(accessions):
        form = forms[i] if i < len(forms) else ""
        if form not in ("10-K", "10-Q", "8-K", "S-4", "10-K/A", "10-Q/A"):
            continue
        pref = accession_cik_prefix(acc)
        if pref != cik and pref not in candidate_ciks:
            candidate_ciks.append(pref)

    best = company
    best_n = n_recent
    for alt in candidate_ciks:
        try:
            n_alt = len(collect_10k_10q_for_cik(alt, ticker=company["ticker"], limit=MAX_FILINGS))
        except Exception:
            continue
        if n_alt > best_n:
            try:
                alt_data = fetch_json(submissions_url(alt), _data_headers())
                alt_name = alt_data.get("name") or company.get("name")
            except Exception:
                alt_name = company.get("name")
            best = {
                "ticker": company["ticker"],
                "cik": alt,
                "name": alt_name,
                "cik_resolution": f"accession_prefix_from_{cik}",
                "mapped_cik_thin": cik,
                "mapped_cik_recent_10k10q": n_recent,
            }
            best_n = n_alt
    return best


def list_recent_filings(
    ticker: str, limit: int = MAX_FILINGS, force: bool = False
) -> list[dict[str, Any]]:
    """Return up to ``limit`` recent 10-K/10-Q filings for a ticker."""
    company = resolve_ticker(ticker, validate_history=True)
    if not force:
        cached = db.list_filings(company["ticker"])
        if len(cached) >= limit:
            return [dict(row) for row in cached][:limit]

    rows = collect_10k_10q_for_cik(company["cik"], ticker=company["ticker"], limit=limit)
    db.upsert_company(company["ticker"], company["cik"], company.get("name") or ticker)
    persist = [{k: v for k, v in r.items() if not str(k).startswith("_")} for r in rows]
    if force:
        # Drop stale ticker→filing links (e.g. XOM Holdings one-filer before CIK recovery)
        db.delete_filings_for_ticker(company["ticker"])
    db.upsert_filings(persist)
    return rows[:limit]


def collect_10k_10q_for_cik(
    cik: str,
    *,
    ticker: str,
    limit: int = MAX_FILINGS,
) -> list[dict[str, Any]]:
    """Collect up to ``limit`` 10-K/10-Q rows for a CIK (recent + filings.files shards).

    - Newest-first
    - Deduped by accession
    - Original forms only (10-K, 10-Q — not amendments)
    """
    data = fetch_json(submissions_url(cik), _data_headers())
    cik_s = cik10(cik)
    name = data.get("name") or ticker
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    used_shard = False

    def ingest(block: dict[str, Any]) -> None:
        forms = block.get("form", []) or []
        for i, form in enumerate(forms):
            if form not in ("10-K", "10-Q"):
                continue
            accession = block["accessionNumber"][i]
            if accession in seen:
                continue
            primary_doc = (block.get("primaryDocument") or [""])[i]
            filed = (block.get("filingDate") or [""])[i]
            report_date = (block.get("reportDate") or [""])[i]
            # Archive path uses the submissions registrant CIK, NOT the accession
            # prefix (prefixes often belong to filing agents → 404s).
            url = filing_archive_url(cik_s, accession, primary_doc)
            seen.add(accession)
            rows.append(
                {
                    "accession": accession,
                    "ticker": ticker,
                    "cik": cik_s,
                    "form": form,
                    "filed": filed,
                    "report_date": report_date,
                    "primary_doc": primary_doc,
                    "filing_url": url,
                }
            )
            if len(rows) >= limit:
                return

    ingest((data.get("filings") or {}).get("recent") or {})
    if len(rows) < limit:
        for meta in (data.get("filings") or {}).get("files") or []:
            shard_name = meta.get("name")
            if not shard_name:
                continue
            shard_url = f"{SEC_BASE}/submissions/{shard_name}"
            try:
                shard = fetch_json(shard_url, _data_headers())
            except Exception:
                continue
            used_shard = True
            # Shards are flat arrays (same keys as recent), not nested under filings.recent
            ingest(shard)
            if len(rows) >= limit:
                break

    rows.sort(key=lambda r: r.get("filed") or "", reverse=True)
    # Attach metadata for audits (not persisted on filings table)
    for r in rows:
        r["_used_archive_shard"] = used_shard
        r["_submissions_cik"] = cik_s
        r["_submissions_name"] = name
    return rows[:limit]


# Back-compat alias used by diagnose scripts / tests
_collect_10k_10q = lambda company, limit: collect_10k_10q_for_cik(  # noqa: E731
    company["cik"], ticker=company["ticker"], limit=limit
)


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
