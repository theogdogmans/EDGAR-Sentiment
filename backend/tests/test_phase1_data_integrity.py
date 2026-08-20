"""Phase 1 data-integrity validation tests (no network required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.edgar.facts import metrics_for_filing  # noqa: E402
from app.extract.mda import extract_from_html  # noqa: E402


def _facts_payload(tag_rows: dict[str, list[dict]]) -> dict:
    """Build a minimal companyfacts-like structure."""
    us_gaap = {}
    for tag, rows in tag_rows.items():
        by_unit: dict[str, list] = {}
        for row in rows:
            item = dict(row)
            unit = item.pop("_unit", "USD")
            by_unit.setdefault(unit, []).append(item)
        us_gaap[tag] = {"units": by_unit}
    return {"facts": {"us-gaap": us_gaap}}


SAMPLE_10K_HTML = """
<html><body>
<p>Table of Contents</p>
<p>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations ..... 40</p>
<p>Item 7A. Quantitative and Qualitative Disclosures About Market Risk ..... 70</p>
<p>Item 8. Financial Statements and Supplementary Data ..... 72</p>
<div>
<p>Item 1. Business</p>
<p>We make phones and computers and related products for customers worldwide.</p>
</div>
<div>
<p>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations</p>
<p>Net sales increased during the year as customer demand remained strong across product categories.</p>
<p>Operating expenses were carefully managed while we continued to invest in research and development.</p>
<p>Liquidity remained adequate to fund capital returns and ongoing operations throughout the fiscal year.</p>
<table><tr><td>Revenue</td><td>100</td><td>Bad table should be stripped</td></tr></table>
<p>We believe our business outlook remains constructive based on the trends described above.</p>
</div>
<div>
<p>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</p>
<p>We are exposed to market risk from changes in foreign currency exchange rates and interest rates.</p>
<p>This market risk discussion must not appear inside the MD&A extraction used for sentiment.</p>
</div>
<div>
<p>Item 8. Financial Statements and Supplementary Data</p>
<p>The audited financial statements appear below.</p>
</div>
</body></html>
"""

SAMPLE_10Q_HTML = """
<html><body>
<p>Item 2. Management's Discussion and Analysis of Financial Condition and Results of Operations</p>
<p>Quarterly revenue increased versus the prior-year quarter on higher unit volumes and average selling prices.</p>
<p>Gross margin expanded as product mix improved and manufacturing costs declined modestly.</p>
<p>Item 3. Quantitative and Qualitative Disclosures About Market Risk</p>
<p>Foreign currency exposures are hedged in the ordinary course of business.</p>
</body></html>
"""

# Modern filings often wrap Item headings in <table>; stripping tables first must not
# erase the MD&A start anchor.
SAMPLE_10Q_HEADING_IN_TABLE = """
<html><body>
<table><tr><td>ITEM 2.</td></tr>
<tr><td>Management's Discussion and Analysis of Financial Condition and Results of Operations</td></tr></table>
<p>Quarterly revenue increased versus the prior-year quarter on higher unit volumes and average selling prices.</p>
<p>Operating income improved as operating expenses remained tightly controlled in the period.</p>
<table><tr><td>ITEM 3.</td></tr>
<tr><td>Quantitative and Qualitative Disclosures About Market Risk</td></tr></table>
<p>Foreign currency exposures are hedged in the ordinary course of business.</p>
</body></html>
"""


def test_10k_mda_stops_before_item_7a():
    result = extract_from_html(SAMPLE_10K_HTML, "10-K")
    text = result["text"].lower()
    assert "net sales increased" in text
    assert "market risk from changes in foreign currency" not in text
    assert "item 7a" not in text
    assert result["status"] == "ok"
    assert "7a" in result["end_heading"].lower() or "quantitative" in result["end_heading"].lower()


def test_10k_mda_strips_tables():
    result = extract_from_html(SAMPLE_10K_HTML, "10-K")
    assert "Bad table should be stripped" not in result["text"]


def test_10k_skips_toc_hit():
    result = extract_from_html(SAMPLE_10K_HTML, "10-K")
    # Real body heading, not TOC page-number line
    assert "40" not in result["start_heading"] or "discussion" in result["start_heading"].lower()
    assert len(result["text"]) > 200


def test_10q_mda_ends_at_item3_quantitative():
    result = extract_from_html(SAMPLE_10Q_HTML, "10-Q")
    assert "quarterly revenue increased" in result["text"].lower()
    assert "foreign currency exposures are hedged" not in result["text"].lower()


def test_10q_heading_inside_table_still_extracts():
    result = extract_from_html(SAMPLE_10Q_HEADING_IN_TABLE, "10-Q")
    text = result["text"].lower()
    assert "quarterly revenue increased" in text
    assert "foreign currency exposures are hedged" not in text
    assert result["status"] == "ok"
    assert result["char_count"] >= 200


def test_10q_selects_quarterly_not_ytd():
    accn = "0000320193-25-000008"
    facts = _facts_payload(
        {
            "RevenueFromContractWithCustomerExcludingAssessedTax": [
                {
                    "accn": accn,
                    "start": "2024-12-29",
                    "end": "2025-03-29",
                    "val": 95_359_000_000,
                    "fy": 2025,
                    "fp": "Q2",
                    "filed": "2025-05-02",
                    "_unit": "USD",
                },
                {
                    "accn": accn,
                    "start": "2024-09-29",
                    "end": "2025-03-29",
                    "val": 200_000_000_000,
                    "fy": 2025,
                    "fp": "Q2",
                    "filed": "2025-05-02",
                    "_unit": "USD",
                },
                {
                    "accn": "0000320193-24-000008",
                    "start": "2023-12-31",
                    "end": "2024-03-30",
                    "val": 90_753_000_000,
                    "fy": 2024,
                    "fp": "Q2",
                    "filed": "2024-05-03",
                    "_unit": "USD",
                },
                {
                    "accn": "0000320193-24-000008",
                    "start": "2023-10-01",
                    "end": "2024-03-30",
                    "val": 180_000_000_000,
                    "fy": 2024,
                    "fp": "Q2",
                    "filed": "2024-05-03",
                    "_unit": "USD",
                },
            ]
        }
    )
    out = metrics_for_filing(facts, accn, "10-Q", report_date="2025-03-29", sector="Information Technology")
    rev = out["revenue"]
    assert rev["status"] == "ok"
    assert 70 <= rev["duration_days"] <= 100
    assert rev["value"] == 95_359_000_000
    assert rev["prior"] == 90_753_000_000
    assert rev["fp"] == "Q2"
    assert rev["prior_fp"] == "Q2"


def test_10q_requires_matching_fp():
    accn = "0000320193-25-000073"
    rows = [
        {"accn": accn, "start": "2025-03-30", "end": "2025-06-28", "val": 94_036_000_000, "fy": 2025, "fp": "Q3", "filed": "2025-08-01", "_unit": "USD"},
        # Prior year but wrong fp (Q2) — should not match
        {"accn": "0000320193-24-000066", "start": "2024-03-31", "end": "2024-06-29", "val": 85_777_000_000, "fy": 2024, "fp": "Q2", "filed": "2024-08-02", "_unit": "USD"},
    ]
    facts = _facts_payload({"NetIncomeLoss": rows})
    out = metrics_for_filing(facts, accn, "10-Q", report_date="2025-06-28", sector="Information Technology")
    assert out["net_income"]["status"] == "unavailable"
    assert out["net_income"]["pct_change"] is None


def test_10k_selects_annual_not_quarterly():
    accn = "0000320193-24-000123"
    rows = [
        # Annual
        {"accn": accn, "start": "2023-10-01", "end": "2024-09-28", "val": 391_035_000_000, "fy": 2024, "fp": "FY", "filed": "2024-11-01", "_unit": "USD"},
        # Quarterly decoy under same accession
        {"accn": accn, "start": "2024-06-30", "end": "2024-09-28", "val": 94_930_000_000, "fy": 2024, "fp": "Q4", "filed": "2024-11-01", "_unit": "USD"},
        # Prior annual
        {"accn": "0000320193-23-000106", "start": "2022-09-25", "end": "2023-09-30", "val": 383_285_000_000, "fy": 2023, "fp": "FY", "filed": "2023-11-03", "_unit": "USD"},
    ]
    facts = _facts_payload({"RevenueFromContractWithCustomerExcludingAssessedTax": rows})
    out = metrics_for_filing(facts, accn, "10-K", report_date="2024-09-28", sector="Information Technology")
    rev = out["revenue"]
    assert rev["status"] == "ok"
    assert 330 <= rev["duration_days"] <= 400
    assert rev["value"] == 391_035_000_000
    assert rev["prior"] == 383_285_000_000


def test_missing_comparison_returns_null():
    accn = "0000320193-25-000999"
    rows = [
        {"accn": accn, "start": "2024-12-29", "end": "2025-03-29", "val": 10.0, "fy": 2025, "fp": "Q2", "filed": "2025-05-02", "_unit": "USD"},
        # No prior-year quarter
    ]
    facts = _facts_payload({"NetIncomeLoss": rows})
    out = metrics_for_filing(facts, accn, "10-Q", report_date="2025-03-29", sector="Information Technology")
    assert out["net_income"]["pct_change"] is None
    assert out["net_income"]["status"] == "unavailable"


def test_financials_revenue_unavailable():
    accn = "0000019617-25-000001"
    facts = _facts_payload(
        {
            "Revenues": [
                {"accn": accn, "start": "2024-01-01", "end": "2024-12-31", "val": 50_000_000_000, "fy": 2024, "fp": "FY", "filed": "2025-02-20", "_unit": "USD"},
                {"accn": "0000019617-24-000001", "start": "2023-01-01", "end": "2023-12-31", "val": 45_000_000_000, "fy": 2023, "fp": "FY", "filed": "2024-02-20", "_unit": "USD"},
            ],
            "NetIncomeLoss": [
                {"accn": accn, "start": "2024-01-01", "end": "2024-12-31", "val": 10_000_000_000, "fy": 2024, "fp": "FY", "filed": "2025-02-20", "_unit": "USD"},
                {"accn": "0000019617-24-000001", "start": "2023-01-01", "end": "2023-12-31", "val": 9_000_000_000, "fy": 2023, "fp": "FY", "filed": "2024-02-20", "_unit": "USD"},
            ],
        }
    )
    out = metrics_for_filing(facts, accn, "10-K", report_date="2024-12-31", sector="Financials")
    assert out["revenue"]["status"] == "unavailable"
    assert out["revenue"]["reason"] == "sector_not_comparable_revenue"
    assert out["revenue"]["pct_change"] is None
    assert out["net_income"]["status"] == "ok"
    assert out["net_income"]["pct_change"] is not None


def test_aapl_like_10q_period_pair():
    """AAPL-shaped Q2 comparison: 91-day current vs prior Q2."""
    accn = "0000320193-25-000008"
    facts = _facts_payload(
        {
            "RevenueFromContractWithCustomerExcludingAssessedTax": [
                {"accn": accn, "start": "2024-12-29", "end": "2025-03-29", "val": 95_359_000_000, "fy": 2025, "fp": "Q2", "filed": "2025-05-02", "_unit": "USD"},
                {"accn": "0000320193-24-000008", "start": "2023-12-31", "end": "2024-03-30", "val": 90_753_000_000, "fy": 2024, "fp": "Q2", "filed": "2024-05-03", "_unit": "USD"},
            ],
            "NetIncomeLoss": [
                {"accn": accn, "start": "2024-12-29", "end": "2025-03-29", "val": 24_780_000_000, "fy": 2025, "fp": "Q2", "filed": "2025-05-02", "_unit": "USD"},
                {"accn": "0000320193-24-000008", "start": "2023-12-31", "end": "2024-03-30", "val": 23_636_000_000, "fy": 2024, "fp": "Q2", "filed": "2024-05-03", "_unit": "USD"},
            ],
        }
    )
    out = metrics_for_filing(facts, accn, "10-Q", report_date="2025-03-29", sector="Information Technology")
    assert out["revenue"]["status"] == "ok"
    assert out["net_income"]["status"] == "ok"
    assert out["revenue"]["fp"] == out["revenue"]["prior_fp"] == "Q2"
    assert abs(out["revenue"]["pct_change"] - ((95_359_000_000 - 90_753_000_000) / 90_753_000_000)) < 1e-9
