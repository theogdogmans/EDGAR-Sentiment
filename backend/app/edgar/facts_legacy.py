from __future__ import annotations

from datetime import date
from typing import Any, Optional

REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
)
INCOME_TAGS = ("NetIncomeLoss",)
OPERATING_TAGS = ("OperatingIncomeLoss",)
EPS_TAGS = ("EarningsPerShareDiluted", "EarningsPerShareBasic")


def _duration_days(row: dict[str, Any]) -> int:
    start, end = row.get("start"), row.get("end")
    if not start or not end:
        return 0
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def _unit_rows(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    node = (
        facts.get("facts", {})
        .get("us-gaap", {})
        .get(tag, {})
        .get("units", {})
    )
    rows: list[dict[str, Any]] = []
    for unit, values in node.items():
        for row in values:
            item = dict(row)
            item["_unit"] = unit
            item["_tag"] = tag
            rows.append(item)
    return rows


def _first_tag_rows(facts: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    for tag in tags:
        rows = _unit_rows(facts, tag)
        if rows:
            return rows
    return []


def _match_accession(
    rows: list[dict[str, Any]], accession: str, form: str
) -> Optional[dict[str, Any]]:
    accn = accession.replace("-", "")
    matches = [
        r
        for r in rows
        if str(r.get("accn", "")).replace("-", "") == accn and r.get("start") and r.get("end")
    ]
    if not matches:
        return None
    # The current filing also restates last year's comparative column under the same accn.
    latest_end = max(r.get("end") or "" for r in matches)
    matches = [r for r in matches if r.get("end") == latest_end]
    target = 91 if form.startswith("10-Q") else 365
    matches.sort(key=lambda r: (abs(_duration_days(r) - target), 0 if "USD" in r["_unit"] else 1))
    return matches[0]


def _prior_period(rows: list[dict[str, Any]], current: dict[str, Any]) -> Optional[dict[str, Any]]:
    end = current.get("end")
    if not end:
        return None
    try:
        current_end = date.fromisoformat(end)
    except ValueError:
        return None
    target_dur = _duration_days(current)
    unit = current.get("_unit")
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        if row.get("_unit") != unit:
            continue
        other_end = row.get("end")
        if not other_end or other_end >= end:
            continue
        if abs(_duration_days(row) - target_dur) > 40:
            continue
        try:
            delta = (current_end - date.fromisoformat(other_end)).days
        except ValueError:
            continue
        if 300 <= delta <= 430:
            scored.append((abs(delta - 365), row))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1].get("filed", "")))
    return scored[0][1]


def _metric(
    facts: dict[str, Any], tags: tuple[str, ...], accession: str, form: str
) -> Optional[dict[str, Any]]:
    rows = _first_tag_rows(facts, tags)
    if not rows:
        return None
    current = _match_accession(rows, accession, form)
    if current is None or current.get("val") is None:
        return None
    prior = _prior_period(rows, current)
    curr_val = float(current["val"])
    prior_val = float(prior["val"]) if prior and prior.get("val") is not None else None
    pct = None
    if prior_val not in (None, 0):
        pct = (curr_val - prior_val) / abs(prior_val)
    return {
        "tag": current["_tag"],
        "value": curr_val,
        "unit": current["_unit"],
        "period_end": current.get("end"),
        "fy": current.get("fy"),
        "fp": current.get("fp"),
        "prior": prior_val,
        "prior_period_end": None if prior is None else prior.get("end"),
        "pct_change": pct,
        "duration_days": _duration_days(current),
    }


def metrics_for_filing(facts: dict[str, Any], accession: str, form: str = "10-K") -> dict[str, Any]:
    return {
        "revenue": _metric(facts, REVENUE_TAGS, accession, form),
        "net_income": _metric(facts, INCOME_TAGS, accession, form),
        "operating_income": _metric(facts, OPERATING_TAGS, accession, form),
        "eps": _metric(facts, EPS_TAGS, accession, form),
    }
