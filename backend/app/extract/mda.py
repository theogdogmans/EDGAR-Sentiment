from __future__ import annotations

import re
from typing import Any

import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .. import db
from ..config import SEC_USER_AGENT
from ..edgar.client import download_filing_html

ITEM7 = re.compile(
    r"item\s*7[\.:]?\s*(?:management|mangement).{0,60}discussion.{0,120}operations",
    re.I | re.S,
)
ITEM8 = re.compile(r"item\s*8[\.:]?\s*financial\s+statements", re.I)
ITEM2 = re.compile(
    r"item\s*2[\.:]?\s*(?:management|mangement).{0,60}discussion.{0,120}operations",
    re.I | re.S,
)
ITEM3 = re.compile(
    r"item\s*3[\.:]?\s*(?:quantitative|defaults|legal)",
    re.I,
)


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = text.replace("\u2019", "'").replace("\xa0", " ").replace("\u00a0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _slice_between(text: str, start_re: re.Pattern[str], end_re: re.Pattern[str]) -> str:
    starts = [m.start() for m in start_re.finditer(text)]
    if not starts:
        return ""
    # Skip table-of-contents hits near the top when a later heading exists.
    cutoff = int(len(text) * 0.08)
    later = [s for s in starts if s >= cutoff]
    start = later[0] if later else starts[-1]
    end_match = end_re.search(text, start + 20)
    end = end_match.start() if end_match else min(len(text), start + 80_000)
    return text[start:end].strip()


def extract_from_html(html: str, form: str) -> str:
    text = _visible_text(html)
    if form.startswith("10-K"):
        chunk = _slice_between(text, ITEM7, ITEM8)
    else:
        chunk = _slice_between(text, ITEM2, ITEM3)
    return chunk


def extract_with_edgartools(filing: dict[str, Any]) -> str:
    try:
        from edgar import Filing, set_identity
    except ImportError:
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
    key = "Item 7" if filing["form"].startswith("10-K") else "Item 2"
    try:
        item = obj[key]
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


def extract_mda(filing: dict[str, Any], force: bool = False) -> tuple[str, str]:
    accession = filing["accession"]
    if not force:
        cached = db.get_mda(accession)
        if cached:
            return cached["text"], cached["source"]

    html = download_filing_html(filing)
    text = extract_from_html(html, filing["form"])
    source = "html"
    if len(text) < 800:
        alt = extract_with_edgartools(filing)
        if len(alt) > len(text):
            text, source = alt, "edgartools"
    if len(text) < 200:
        raise ValueError("Could not extract MD&A text from this filing")
    db.set_mda(accession, text, source)
    return text, source
