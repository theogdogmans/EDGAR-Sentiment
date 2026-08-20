from __future__ import annotations

import re
from typing import Any

from .mda import _slice_between, _visible_text
from .. import db
from ..config import SEC_USER_AGENT
from ..edgar.client import download_filing_html

# 10-K Item 1A Risk Factors → Item 1B or Item 2
ITEM1A = re.compile(
    r"item\s*1a[\.:]?\s*risk\s+factors",
    re.I,
)
ITEM1A_END = re.compile(
    r"item\s*1b[\.:]?|item\s*2[\.:]?\s*(?:properties|unresolved)",
    re.I,
)


def extract_risk_from_html(html: str, form: str) -> str:
    """Item 1A exists on 10-K (and some 10-K/A). Quarterly filings often omit it."""
    if not form.startswith("10-K"):
        return ""
    text = _visible_text(html)
    return _slice_between(text, ITEM1A, ITEM1A_END)


def extract_risk_edgartools(filing: dict[str, Any]) -> str:
    try:
        from edgar import Filing, set_identity
    except ImportError:
        return ""
    if not str(filing.get("form", "")).startswith("10-K"):
        return ""
    set_identity(SEC_USER_AGENT)
    obj = Filing(
        company=filing.get("ticker", ""),
        cik=int(str(filing["cik"]).lstrip("0") or "0"),
        form=filing["form"],
        filing_date=filing["filed"],
        accession_no=filing["accession"],
    ).obj()
    if obj is None:
        return ""
    try:
        item = obj["Item 1A"]
    except Exception:
        return ""
    if item is None:
        return ""
    if hasattr(item, "text"):
        try:
            return str(item.text()).strip()
        except Exception:
            pass
    return str(item).strip()


def extract_risk_factors(filing: dict[str, Any], force: bool = False) -> tuple[str, str]:
    """Extract Item 1A for bias demos only. Cached in mda table with source prefix risk:."""
    accession = filing["accession"]
    cache_key = f"risk:{accession}"
    if not force:
        cached = db.get_mda(cache_key)
        if cached:
            return cached["text"], cached["source"]

    html = download_filing_html(filing)
    text = extract_risk_from_html(html, filing["form"])
    source = "html"
    if len(text) < 400:
        alt = extract_risk_edgartools(filing)
        if len(alt) > len(text):
            text, source = alt, "edgartools"
    if len(text) < 200:
        raise ValueError("Could not extract Item 1A Risk Factors from this filing")
    db.set_mda(cache_key, text, f"risk:{source}")
    return text, source
