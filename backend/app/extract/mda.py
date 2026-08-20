from __future__ import annotations

import re
from typing import Any, Optional

import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .. import db
from ..config import SEC_USER_AGENT

# 10-K Item 7 MD&A
ITEM7 = re.compile(
    r"^\s*item\s*7[\.:]?\s*(?:management|mangement).{0,80}discussion.{0,120}operations",
    re.I | re.M,
)
# Prefer ending at Item 7A (exclude market-risk section from MD&A).
ITEM7A = re.compile(
    r"^\s*item\s*7a[\.:]?\s*(?:quantitative|qualitative|market)",
    re.I | re.M,
)
ITEM8 = re.compile(
    r"^\s*item\s*8[\.:]?\s*financial\s+statements",
    re.I | re.M,
)

# 10-Q Item 2 MD&A → Part I Item 3 Quantitative (not Part II Item 3 Defaults)
ITEM2 = re.compile(
    r"^\s*item\s*2[\.:]?\s*(?:management|mangement).{0,80}discussion.{0,120}operations",
    re.I | re.M,
)
ITEM3_Q = re.compile(
    r"^\s*item\s*3[\.:]?\s*(?:quantitative|qualitative)",
    re.I | re.M,
)

TOC_DOT_LEADER = re.compile(r"\.{4,}|·{4,}|\s{4,}\d+\s*$")
HEADING_LINE = re.compile(r"^\s*item\s*\d+[a-z]?[\.:]?", re.I)


def _visible_text(html: str, *, strip_tables: bool = True) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    if strip_tables:
        for tag in soup.find_all("table"):
            tag.decompose()
    text = soup.get_text("\n")
    text = text.replace("\u2019", "'").replace("\xa0", " ").replace("\u00a0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _line_at(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    if end < 0:
        end = min(len(text), pos + 160)
    return text[start:end].strip()


def _looks_like_toc_hit(text: str, pos: int) -> bool:
    """TOC rows often have dot leaders or a page number on the same line."""
    line = _line_at(text, pos)
    if TOC_DOT_LEADER.search(line):
        return True
    # Very short "Item 7 ... Operations 42" style
    if len(line) < 120 and re.search(r"\d+\s*$", line) and "discussion" in line.lower():
        # Could still be a real heading; check following content density
        window = text[pos : pos + 400]
        next_items = list(HEADING_LINE.finditer(window))
        # Multiple Item headings packed tightly ⇒ TOC block
        if len(next_items) >= 3:
            return True
    # Cluster of Item headings within next 600 chars ⇒ TOC
    window = text[pos : pos + 600]
    if len(list(HEADING_LINE.finditer(window))) >= 4:
        return True
    return False


def _find_starts(text: str, start_re: re.Pattern[str]) -> list[int]:
    starts = [m.start() for m in start_re.finditer(text)]
    # Drop TOC-like hits
    filtered = [s for s in starts if not _looks_like_toc_hit(text, s)]
    return filtered or starts


def _pick_start(text: str, starts: list[int]) -> Optional[int]:
    if not starts:
        return None
    # Prefer matches after the early TOC region, but not so late we miss real MD&A.
    cutoff = int(len(text) * 0.05)
    later = [s for s in starts if s >= cutoff]
    if later:
        # Prefer the first non-TOC hit in the body
        return later[0]
    return starts[-1]


def _pick_end(text: str, start: int, end_res: list[re.Pattern[str]]) -> tuple[int, str]:
    """Return (end_pos, end_heading). First matching end pattern after start wins."""
    best_pos: Optional[int] = None
    best_heading = ""
    for end_re in end_res:
        for m in end_re.finditer(text, start + 40):
            if _looks_like_toc_hit(text, m.start()):
                continue
            pos = m.start()
            if best_pos is None or pos < best_pos:
                best_pos = pos
                best_heading = _line_at(text, pos)
            break  # first non-TOC hit for this pattern
    if best_pos is None:
        # Cap runaway extraction
        return min(len(text), start + 80_000), ""
    return best_pos, best_heading


def extract_from_html(html: str, form: str) -> dict[str, Any]:
    text = _visible_text(html, strip_tables=True)
    if form.startswith("10-K"):
        starts = _find_starts(text, ITEM7)
        start = _pick_start(text, starts)
        if start is None:
            return {
                "text": "",
                "char_count": 0,
                "start_heading": "",
                "end_heading": "",
                "status": "no_start_heading",
            }
        # End at Item 7A if present, else Item 8
        end, end_heading = _pick_end(text, start, [ITEM7A, ITEM8])
        start_heading = _line_at(text, start)
        chunk = text[start:end].strip()
        # Guard: if 7A heading appears after the MD&A opening, trim there
        for m in ITEM7A.finditer(chunk):
            if m.start() > 80:
                end_heading = _line_at(chunk, m.start()) or end_heading
                chunk = chunk[: m.start()].strip()
                break
        status = "ok" if len(chunk) >= 200 else "too_short"
        return {
            "text": chunk,
            "char_count": len(chunk),
            "start_heading": start_heading,
            "end_heading": end_heading,
            "status": status,
        }

    # 10-Q
    starts = _find_starts(text, ITEM2)
    start = _pick_start(text, starts)
    if start is None:
        return {
            "text": "",
            "char_count": 0,
            "start_heading": "",
            "end_heading": "",
            "status": "no_start_heading",
        }
    end, end_heading = _pick_end(text, start, [ITEM3_Q])
    start_heading = _line_at(text, start)
    chunk = text[start:end].strip()
    status = "ok" if len(chunk) >= 200 else "too_short"
    return {
        "text": chunk,
        "char_count": len(chunk),
        "start_heading": start_heading,
        "end_heading": end_heading,
        "status": status,
    }


def extract_with_edgartools(filing: dict[str, Any]) -> dict[str, Any]:
    try:
        from edgar import Filing, set_identity
    except ImportError:
        return {"text": "", "start_heading": "", "end_heading": "", "status": "edgartools_unavailable"}

    set_identity(SEC_USER_AGENT)
    obj = Filing(
        company=filing.get("ticker", ""),
        cik=int(str(filing["cik"]).lstrip("0") or "0"),
        form=filing["form"],
        filing_date=filing["filed"],
        accession_no=filing["accession"],
    ).obj()
    if obj is None:
        return {"text": "", "start_heading": "", "end_heading": "", "status": "edgartools_no_obj"}
    key = "Item 7" if filing["form"].startswith("10-K") else "Item 2"
    try:
        item = obj[key]
    except Exception:
        return {"text": "", "start_heading": key, "end_heading": "", "status": "edgartools_no_item"}
    if item is None:
        return {"text": "", "start_heading": key, "end_heading": "", "status": "edgartools_no_item"}
    if hasattr(item, "text"):
        try:
            text = str(item.text()).strip()
        except Exception:
            text = str(item).strip()
    else:
        text = str(item).strip()

    end_heading = ""
    if filing["form"].startswith("10-K"):
        # edgartools Item 7 should already exclude 7A; still trim if 7A leaked in
        m = ITEM7A.search(text)
        if m:
            text = text[: m.start()].strip()
            end_heading = "Item 7A (trimmed)"
        else:
            end_heading = "Item 8 (section boundary)"
    else:
        end_heading = "Item 3 (section boundary)"

    status = "ok" if len(text) >= 200 else "too_short"
    return {
        "text": text,
        "start_heading": key,
        "end_heading": end_heading,
        "status": status,
    }


def _quality_score(result: dict[str, Any], form: str) -> float:
    """Higher is better. Used to choose between HTML and edgartools extractions."""
    text = result.get("text") or ""
    if len(text) < 200:
        return -1.0
    score = 0.0
    start_h = (result.get("start_heading") or "").lower()
    end_h = (result.get("end_heading") or "").lower()
    if form.startswith("10-K"):
        if "item 7" in start_h and "7a" not in start_h[:20]:
            score += 3.0
        if "7a" in end_h or "item 8" in end_h:
            score += 2.0
        # Penalize if Item 7A body still dominates
        if re.search(r"item\s*7a", text[500:], re.I):
            score -= 4.0
    else:
        if "item 2" in start_h:
            score += 3.0
        if "item 3" in end_h or "quantitative" in end_h:
            score += 2.0
    # Prefer substantial but not absurd lengths
    n = len(text)
    if 2_000 <= n <= 200_000:
        score += 2.0
    elif n > 200_000:
        score -= 1.0
    if result.get("status") == "ok":
        score += 1.0
    return score


def extract_mda(filing: dict[str, Any], force: bool = False) -> tuple[str, dict[str, Any]]:
    """
    Returns (text, metadata) where metadata includes:
      source, char_count, start_heading, end_heading, status, confidence
    """
    accession = filing["accession"]
    if not force:
        cached = db.get_mda(accession)
        if cached:
            keys = set(cached.keys())
            meta = {
                "source": cached["source"],
                "char_count": len(cached["text"]),
                "start_heading": cached["start_heading"] if "start_heading" in keys else "",
                "end_heading": cached["end_heading"] if "end_heading" in keys else "",
                "status": cached["status"] if "status" in keys else "cached",
                "confidence": cached["confidence"] if "confidence" in keys else "unknown",
            }
            return cached["text"], meta

    from ..edgar.client import download_filing_html

    html = download_filing_html(filing)
    html_result = extract_from_html(html, filing["form"])
    edgar_result = extract_with_edgartools(filing)

    html_q = _quality_score(html_result, filing["form"])
    edgar_q = _quality_score(edgar_result, filing["form"])

    if edgar_q > html_q:
        chosen, source = edgar_result, "edgartools"
        confidence = "high" if edgar_q >= 5 else "medium"
    elif html_q >= 0:
        chosen, source = html_result, "html"
        # Long HTML that barely passes quality is medium; strong heading match is high
        confidence = "high" if html_q >= 6 else "medium" if html_q >= 3 else "low"
    elif edgar_q >= 0:
        chosen, source = edgar_result, "edgartools"
        confidence = "medium"
    else:
        raise ValueError("Could not extract MD&A text from this filing")

    text = chosen["text"]
    if len(text) < 200:
        raise ValueError("Could not extract MD&A text from this filing")

    meta = {
        "source": source,
        "char_count": len(text),
        "start_heading": chosen.get("start_heading") or "",
        "end_heading": chosen.get("end_heading") or "",
        "status": chosen.get("status") or "ok",
        "confidence": confidence,
        "html_quality": html_q,
        "edgartools_quality": edgar_q,
    }
    db.set_mda(
        accession,
        text,
        source,
        start_heading=meta["start_heading"],
        end_heading=meta["end_heading"],
        status=meta["status"],
        confidence=meta["confidence"],
    )
    return text, meta
