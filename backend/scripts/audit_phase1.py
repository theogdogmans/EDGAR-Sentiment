#!/usr/bin/env python3
"""BEFORE (legacy) vs AFTER (Phase 1) audit for MD&A + XBRL period matching."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.edgar import facts as facts_new
from app.edgar import facts_legacy
from app.extract import mda as mda_new
from app.extract import mda_legacy


SAMPLE_10K_HTML = """
<html><body>
<p>Table of Contents</p>
<p>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations ..... 40</p>
<p>Item 7A. Quantitative and Qualitative Disclosures About Market Risk ..... 70</p>
<p>Item 8. Financial Statements and Supplementary Data ..... 72</p>
<div>
<p>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations</p>
<p>Net sales increased during the year as customer demand remained strong across product categories.</p>
<p>Operating expenses were carefully managed while we continued to invest in research and development.</p>
<p>Liquidity remained adequate to fund capital returns and ongoing operations throughout the fiscal year.</p>
<p>We believe our business outlook remains constructive based on the trends described above.</p>
</div>
<div>
<p>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</p>
<p>We are exposed to market risk from changes in foreign currency exchange rates and interest rates.</p>
<p>MARKET_RISK_MARKER_SHOULD_NOT_APPEAR_IN_NEW_MDA</p>
</div>
<div>
<p>Item 8. Financial Statements and Supplementary Data</p>
<p>The audited financial statements appear below.</p>
</div>
</body></html>
"""


def _payload(tag_rows):
    us_gaap = {}
    for tag, rows in tag_rows.items():
        by_unit = {}
        for row in rows:
            item = dict(row)
            unit = item.pop("_unit", "USD")
            by_unit.setdefault(unit, []).append(item)
        us_gaap[tag] = {"units": by_unit}
    return {"facts": {"us-gaap": us_gaap}}


def _fmt_metric(m):
    if not m:
        return {"status": "missing"}
    return {
        "status": m.get("status", "ok" if m.get("pct_change") is not None else "legacy"),
        "reason": m.get("reason"),
        "duration": m.get("duration_days"),
        "value": m.get("value"),
        "prior": m.get("prior"),
        "pct": m.get("pct_change"),
        "fp": m.get("fp"),
        "prior_fp": m.get("prior_fp"),
    }


FILINGS = [
    {
        "label": "AAPL-like 10-Q (quarterly + YTD decoys)",
        "form": "10-Q",
        "report_date": "2025-03-29",
        "sector": "Information Technology",
        "accession": "0000320193-25-000008",
        "facts": _payload(
            {
                "RevenueFromContractWithCustomerExcludingAssessedTax": [
                    {"accn": "0000320193-25-000008", "start": "2024-12-29", "end": "2025-03-29", "val": 95_359_000_000, "fy": 2025, "fp": "Q2", "filed": "2025-05-02", "_unit": "USD"},
                    {"accn": "0000320193-25-000008", "start": "2024-09-29", "end": "2025-03-29", "val": 200_000_000_000, "fy": 2025, "fp": "Q2", "filed": "2025-05-02", "_unit": "USD"},
                    {"accn": "0000320193-24-000008", "start": "2023-12-31", "end": "2024-03-30", "val": 90_753_000_000, "fy": 2024, "fp": "Q2", "filed": "2024-05-03", "_unit": "USD"},
                    {"accn": "0000320193-24-000008", "start": "2023-10-01", "end": "2024-03-30", "val": 180_000_000_000, "fy": 2024, "fp": "Q2", "filed": "2024-05-03", "_unit": "USD"},
                ],
                "NetIncomeLoss": [
                    {"accn": "0000320193-25-000008", "start": "2024-12-29", "end": "2025-03-29", "val": 24_780_000_000, "fy": 2025, "fp": "Q2", "filed": "2025-05-02", "_unit": "USD"},
                    {"accn": "0000320193-25-000008", "start": "2024-09-29", "end": "2025-03-29", "val": 50_000_000_000, "fy": 2025, "fp": "Q2", "filed": "2025-05-02", "_unit": "USD"},
                    {"accn": "0000320193-24-000008", "start": "2023-12-31", "end": "2024-03-30", "val": 23_636_000_000, "fy": 2024, "fp": "Q2", "filed": "2024-05-03", "_unit": "USD"},
                ],
            }
        ),
    },
    {
        "label": "AAPL-like 10-K (annual + quarterly decoy)",
        "form": "10-K",
        "report_date": "2024-09-28",
        "sector": "Information Technology",
        "accession": "0000320193-24-000123",
        "facts": _payload(
            {
                "RevenueFromContractWithCustomerExcludingAssessedTax": [
                    {"accn": "0000320193-24-000123", "start": "2023-10-01", "end": "2024-09-28", "val": 391_035_000_000, "fy": 2024, "fp": "FY", "filed": "2024-11-01", "_unit": "USD"},
                    {"accn": "0000320193-24-000123", "start": "2024-06-30", "end": "2024-09-28", "val": 94_930_000_000, "fy": 2024, "fp": "Q4", "filed": "2024-11-01", "_unit": "USD"},
                    {"accn": "0000320193-23-000106", "start": "2022-09-25", "end": "2023-09-30", "val": 383_285_000_000, "fy": 2023, "fp": "FY", "filed": "2023-11-03", "_unit": "USD"},
                ],
                "NetIncomeLoss": [
                    {"accn": "0000320193-24-000123", "start": "2023-10-01", "end": "2024-09-28", "val": 93_736_000_000, "fy": 2024, "fp": "FY", "filed": "2024-11-01", "_unit": "USD"},
                    {"accn": "0000320193-23-000106", "start": "2022-09-25", "end": "2023-09-30", "val": 96_995_000_000, "fy": 2023, "fp": "FY", "filed": "2023-11-03", "_unit": "USD"},
                ],
            }
        ),
    },
    {
        "label": "10-Q with only YTD facts (should disappear AFTER)",
        "form": "10-Q",
        "report_date": "2025-03-29",
        "sector": "Information Technology",
        "accession": "0000320193-25-YTDONLY",
        "facts": _payload(
            {
                "NetIncomeLoss": [
                    {"accn": "0000320193-25-YTDONLY", "start": "2024-09-29", "end": "2025-03-29", "val": 50_000_000_000, "fy": 2025, "fp": "Q2", "filed": "2025-05-02", "_unit": "USD"},
                    {"accn": "0000320193-24-YTDONLY", "start": "2023-10-01", "end": "2024-03-30", "val": 45_000_000_000, "fy": 2024, "fp": "Q2", "filed": "2024-05-03", "_unit": "USD"},
                ],
            }
        ),
    },
    {
        "label": "Financials bank 10-K (revenue should disappear AFTER)",
        "form": "10-K",
        "report_date": "2024-12-31",
        "sector": "Financials",
        "accession": "0000019617-25-000001",
        "facts": _payload(
            {
                "Revenues": [
                    {"accn": "0000019617-25-000001", "start": "2024-01-01", "end": "2024-12-31", "val": 50_000_000_000, "fy": 2024, "fp": "FY", "filed": "2025-02-20", "_unit": "USD"},
                    {"accn": "0000019617-24-000001", "start": "2023-01-01", "end": "2023-12-31", "val": 45_000_000_000, "fy": 2023, "fp": "FY", "filed": "2024-02-20", "_unit": "USD"},
                ],
                "NetIncomeLoss": [
                    {"accn": "0000019617-25-000001", "start": "2024-01-01", "end": "2024-12-31", "val": 10_000_000_000, "fy": 2024, "fp": "FY", "filed": "2025-02-20", "_unit": "USD"},
                    {"accn": "0000019617-24-000001", "start": "2023-01-01", "end": "2023-12-31", "val": 9_000_000_000, "fy": 2023, "fp": "FY", "filed": "2024-02-20", "_unit": "USD"},
                ],
            }
        ),
    },
]


def audit_mda():
    print("=" * 72)
    print("MD&A EXTRACTION — SAMPLE 10-K HTML")
    print("=" * 72)
    legacy_text = mda_legacy.extract_from_html(SAMPLE_10K_HTML, "10-K")
    new = mda_new.extract_from_html(SAMPLE_10K_HTML, "10-K")
    print(f"BEFORE chars: {len(legacy_text)}")
    print(f"BEFORE contains Item 7A market-risk marker: {'MARKET_RISK_MARKER' in legacy_text}")
    print(f"AFTER  chars: {new['char_count'] if 'char_count' in new else len(new['text'])}")
    print(f"AFTER  start: {new.get('start_heading')}")
    print(f"AFTER  end:   {new.get('end_heading')}")
    print(f"AFTER  status:{new.get('status')}")
    print(f"AFTER contains Item 7A market-risk marker: {'MARKET_RISK_MARKER' in new['text']}")
    print()


def audit_metrics():
    print("=" * 72)
    print("XBRL METRICS — BEFORE (legacy) vs AFTER (Phase 1)")
    print("=" * 72)
    disappeared = []
    for case in FILINGS:
        print("-" * 72)
        print(case["label"])
        print(f"form={case['form']} report_date={case['report_date']} sector={case['sector']}")
        before = facts_legacy.metrics_for_filing(case["facts"], case["accession"], case["form"])
        after = facts_new.metrics_for_filing(
            case["facts"],
            case["accession"],
            case["form"],
            report_date=case["report_date"],
            sector=case["sector"],
        )
        for key in ("revenue", "net_income"):
            b = _fmt_metric(before.get(key))
            a = _fmt_metric(after.get(key))
            print(f"  {key}:")
            print(f"    BEFORE duration={b.get('duration')} value={b.get('value')} prior={b.get('prior')} pct={b.get('pct')}")
            print(f"    AFTER  duration={a.get('duration')} value={a.get('value')} prior={a.get('prior')} pct={a.get('pct')} status={a.get('status')} reason={a.get('reason')}")
            before_ok = b.get("pct") is not None
            after_ok = a.get("pct") is not None
            if before_ok and not after_ok:
                disappeared.append(f"{case['label']} / {key}")
        print()
    print("=" * 72)
    print("OBSERVATIONS THAT DISAPPEARED UNDER STRICTER VALIDATION")
    print("=" * 72)
    if not disappeared:
        print("(none in this synthetic set)")
    else:
        for item in disappeared:
            print(f" - {item}")
    print()


def try_live_aapl():
    print("=" * 72)
    print("LIVE AAPL COMPANYFACTS (if network available)")
    print("=" * 72)
    try:
        import httpx
    except ImportError:
        print("httpx not installed — skip live AAPL pull")
        return
    from app.edgar.facts import _duration_days, _unit_rows

    cik = "0000320193"
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    headers = {"User-Agent": "edgar-sentiment-audit/0.1 (Josh joshpottsjk@gmail.com)"}
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            facts = resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"Could not fetch live facts: {exc}")
        return

    # Discover real accessions by period end (not guessed accession numbers).
    rows = _unit_rows(facts, "NetIncomeLoss")
    targets = [
        ("10-K", "2024-09-28", (330, 400)),
        ("10-Q", "2025-03-29", (70, 100)),
        ("10-Q", "2025-06-28", (70, 100)),
    ]
    for form, report, band in targets:
        lo, hi = band
        matches = [
            r
            for r in rows
            if r.get("end") == report and lo <= _duration_days(r) <= hi and r.get("accn")
        ]
        if not matches:
            print(f"\n{form} reportDate={report}: no NetIncomeLoss fact found in band")
            continue
        matches.sort(key=lambda r: r.get("filed") or "", reverse=True)
        accn = str(matches[0]["accn"])
        before = facts_legacy.metrics_for_filing(facts, accn, form)
        after = facts_new.metrics_for_filing(
            facts, accn, form, report_date=report, sector="Information Technology"
        )
        print(f"\n{form} accession={accn} reportDate={report}")
        for key in ("revenue", "net_income"):
            b, a = before.get(key) or {}, after.get(key) or {}
            print(
                f"  {key}: BEFORE dur={b.get('duration_days')} val={b.get('value')} prior={b.get('prior')} pct={b.get('pct_change')}"
            )
            print(
                f"         AFTER  dur={a.get('duration_days')} val={a.get('value')} prior={a.get('prior')} pct={a.get('pct_change')} "
                f"status={a.get('status')} reason={a.get('reason')} end_heading_n/a"
            )


if __name__ == "__main__":
    audit_mda()
    audit_metrics()
    try_live_aapl()
