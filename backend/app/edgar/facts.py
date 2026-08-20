from __future__ import annotations

from datetime import date, timedelta
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

# Hard duration bands — no silent YTD / quarterly substitution.
Q_DURATION = (70, 100)
A_DURATION = (330, 400)
REPORT_DATE_TOLERANCE_DAYS = 15

# GICS sectors where ASC-606-style "revenue" is often non-comparable.
NON_COMPARABLE_REVENUE_SECTORS = frozenset(
    {
        "Financials",
        "Real Estate",
    }
)


def _duration_days(row: dict[str, Any]) -> int:
    start, end = row.get("start"), row.get("end")
    if not start or not end:
        return 0
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


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


def _duration_band(form: str) -> tuple[int, int]:
    if form.startswith("10-Q"):
        return Q_DURATION
    return A_DURATION


def _in_band(days: int, form: str) -> bool:
    lo, hi = _duration_band(form)
    return lo <= days <= hi


def _is_usd_unit(unit: str) -> bool:
    u = (unit or "").upper()
    if "SHARE" in u:
        return False
    return "USD" in u


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "tag": None,
        "value": None,
        "unit": None,
        "period_end": None,
        "fy": None,
        "fp": None,
        "prior": None,
        "prior_period_end": None,
        "prior_fp": None,
        "prior_fy": None,
        "pct_change": None,
        "duration_days": None,
        "prior_duration_days": None,
        "status": "unavailable",
        "reason": reason,
    }


def _ok_metric(
    current: dict[str, Any],
    prior: dict[str, Any],
    pct: Optional[float],
) -> dict[str, Any]:
    return {
        "tag": current["_tag"],
        "value": float(current["val"]),
        "unit": current["_unit"],
        "period_end": current.get("end"),
        "fy": current.get("fy"),
        "fp": current.get("fp"),
        "prior": float(prior["val"]),
        "prior_period_end": prior.get("end"),
        "prior_fp": prior.get("fp"),
        "prior_fy": prior.get("fy"),
        "pct_change": pct,
        "duration_days": _duration_days(current),
        "prior_duration_days": _duration_days(prior),
        "status": "ok",
        "reason": None,
    }


def _accession_candidates(
    rows: list[dict[str, Any]], accession: str, form: str, report_date: Optional[str]
) -> list[dict[str, Any]]:
    accn = accession.replace("-", "")
    report = _parse_date(report_date)
    lo, hi = _duration_band(form)
    matches: list[dict[str, Any]] = []
    for r in rows:
        if str(r.get("accn", "")).replace("-", "") != accn:
            continue
        if not r.get("start") or not r.get("end") or r.get("val") is None:
            continue
        if not _is_usd_unit(str(r.get("_unit", ""))):
            continue
        days = _duration_days(r)
        if not (lo <= days <= hi):
            continue
        matches.append(r)
    if not matches:
        return []

    # Prefer end date close to filing reportDate, then closer to band center.
    center = (lo + hi) / 2.0

    def sort_key(r: dict[str, Any]) -> tuple:
        end = _parse_date(r.get("end"))
        if report and end:
            delta = abs((end - report).days)
        else:
            delta = 10_000
        return (delta, abs(_duration_days(r) - center), 0 if "USD" == str(r.get("_unit", "")).upper() else 1)

    matches.sort(key=sort_key)
    # Keep only those within report-date tolerance when reportDate is known
    if report:
        tight = []
        for r in matches:
            end = _parse_date(r.get("end"))
            if end is not None and abs((end - report).days) <= REPORT_DATE_TOLERANCE_DAYS:
                tight.append(r)
        if tight:
            return tight
        # If nothing is close to reportDate, do not guess
        return []
    return matches


def _prior_period(
    rows: list[dict[str, Any]],
    current: dict[str, Any],
    form: str,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Return (prior_row, error_reason)."""
    end = current.get("end")
    current_end = _parse_date(end)
    if current_end is None:
        return None, "current_missing_end_date"

    target_dur = _duration_days(current)
    if not _in_band(target_dur, form):
        return None, "current_duration_out_of_band"

    unit = current.get("_unit")
    cur_fp = current.get("fp")
    cur_fy = current.get("fy")
    scored: list[tuple[tuple, dict[str, Any]]] = []

    for row in rows:
        if row.get("_unit") != unit:
            continue
        if row.get("val") is None:
            continue
        other_end = _parse_date(row.get("end"))
        if other_end is None or other_end >= current_end:
            continue
        other_dur = _duration_days(row)
        if not _in_band(other_dur, form):
            continue
        # Same duration band as current (already enforced); also keep durations similar
        if abs(other_dur - target_dur) > 25:
            continue
        delta = (current_end - other_end).days
        if not (300 <= delta <= 430):
            continue
        # Require fp match when both present
        other_fp = row.get("fp")
        if cur_fp and other_fp and str(cur_fp) != str(other_fp):
            continue
        # Fiscal year: prefer fy-1 when both present
        other_fy = row.get("fy")
        fy_penalty = 0
        if cur_fy is not None and other_fy is not None:
            try:
                if int(other_fy) != int(cur_fy) - 1:
                    # Ambiguous FY relationship (e.g. fiscal-year change)
                    if form.startswith("10-K"):
                        continue
                    fy_penalty = 5
            except (TypeError, ValueError):
                fy_penalty = 2
        scored.append(((abs(delta - 365) + fy_penalty, abs(other_dur - target_dur), row.get("filed", "")), row))

    if not scored:
        # Distinguish FY ambiguity when candidates existed but fy filter removed them
        return None, "no_valid_prior_period"

    scored.sort(key=lambda item: item[0])
    best = scored[0][1]

    # Extra 10-K check: if fy present and not prior year, reject
    if form.startswith("10-K") and cur_fy is not None and best.get("fy") is not None:
        try:
            if int(best["fy"]) != int(cur_fy) - 1:
                return None, "fiscal_year_change_or_mismatch"
        except (TypeError, ValueError):
            return None, "fiscal_year_unparseable"

    return best, None


def _metric_for_tag(
    facts: dict[str, Any],
    tag: str,
    accession: str,
    form: str,
    report_date: Optional[str],
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    rows = _unit_rows(facts, tag)
    if not rows:
        return None, "tag_absent"
    candidates = _accession_candidates(rows, accession, form, report_date)
    if not candidates:
        # Diagnose
        accn = accession.replace("-", "")
        any_accn = [
            r
            for r in rows
            if str(r.get("accn", "")).replace("-", "") == accn and r.get("start") and r.get("end")
        ]
        if not any_accn:
            return None, "no_fact_for_accession"
        banded = [r for r in any_accn if _in_band(_duration_days(r), form)]
        if not banded:
            return None, "no_fact_in_duration_band"
        return None, "no_fact_near_report_date"

    current = candidates[0]
    prior, prior_err = _prior_period(rows, current, form)
    if prior is None:
        return None, prior_err or "no_valid_prior_period"
    if prior.get("val") is None:
        return None, "prior_missing_value"
    curr_val = float(current["val"])
    prior_val = float(prior["val"])
    pct = None
    if prior_val != 0:
        pct = (curr_val - prior_val) / abs(prior_val)
    return _ok_metric(current, prior, pct), None


def _metric(
    facts: dict[str, Any],
    tags: tuple[str, ...],
    accession: str,
    form: str,
    report_date: Optional[str] = None,
    *,
    per_accession_tag: bool = True,
) -> dict[str, Any]:
    """
    Select the best concept that satisfies period rules for this accession.
    When per_accession_tag is True (revenue), try tags until one yields a valid pair.
    """
    reason_rank = {
        "ok": 100,
        "no_fact_near_report_date": 50,
        "no_valid_prior_period": 45,
        "fiscal_year_change_or_mismatch": 44,
        "no_fact_in_duration_band": 40,
        "no_fact_for_accession": 30,
        "prior_missing_value": 25,
        "current_duration_out_of_band": 20,
        "current_missing_end_date": 15,
        "fiscal_year_unparseable": 12,
        "tag_absent": 5,
        "no_tags": 0,
    }
    last_reason = "no_tags"
    tags_to_try = tags if per_accession_tag else tags[:1]
    # For single-concept path still scan until a tag exists
    if not per_accession_tag:
        tags_to_try = tags

    for tag in tags_to_try:
        metric, reason = _metric_for_tag(facts, tag, accession, form, report_date)
        if metric is not None:
            return metric
        reason = reason or "no_tags"
        if reason_rank.get(reason, 0) >= reason_rank.get(last_reason, 0):
            last_reason = reason
        if not per_accession_tag and reason != "tag_absent":
            break
    return _unavailable(last_reason)


def metrics_for_filing(
    facts: dict[str, Any],
    accession: str,
    form: str = "10-K",
    *,
    report_date: Optional[str] = None,
    sector: Optional[str] = None,
) -> dict[str, Any]:
    sector_name = (sector or "").strip()
    revenue: dict[str, Any]
    if sector_name in NON_COMPARABLE_REVENUE_SECTORS:
        revenue = _unavailable("sector_not_comparable_revenue")
    else:
        revenue = _metric(
            facts,
            REVENUE_TAGS,
            accession,
            form,
            report_date,
            per_accession_tag=True,
        )

    return {
        "revenue": revenue,
        "net_income": _metric(
            facts,
            INCOME_TAGS,
            accession,
            form,
            report_date,
            per_accession_tag=False,
        ),
        "operating_income": _metric(
            facts,
            OPERATING_TAGS,
            accession,
            form,
            report_date,
            per_accession_tag=False,
        ),
        "eps": _metric(
            facts,
            EPS_TAGS,
            accession,
            form,
            report_date,
            per_accession_tag=False,
        ),
    }
