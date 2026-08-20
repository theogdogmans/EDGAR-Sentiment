"""Filing-level agreement helpers and summary APIs.

Phase 1–compatible ``summarize`` (pooled Pearson, n>=3) is retained as the
legacy / exploratory baseline used by production sync until Phase 3.

Phase 2 statistics live in ``summarize_phase2`` / ``stats_core``.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
from scipy.stats import pearsonr

from .stats_core import (
    FORM_10K,
    FORM_10Q,
    FORM_COMBINED,
    MIN_N_CORRELATION,
    NEUTRAL_SENTIMENT,
    NEUTRAL_YOY,
    agreement_counts,
    analyze_pairs,
    form_bucket,
)


NEUTRAL_SENTIMENT_THRESHOLD = NEUTRAL_SENTIMENT
NEUTRAL_YOY_THRESHOLD = NEUTRAL_YOY


def agreement(
    sentiment: float,
    pct_change: Optional[float],
    *,
    sentiment_neutral: float = NEUTRAL_SENTIMENT,
    yoy_neutral: float = NEUTRAL_YOY,
) -> Optional[bool]:
    if pct_change is None:
        return None
    if abs(sentiment) < sentiment_neutral or abs(pct_change) < yoy_neutral:
        return None
    return (sentiment > 0) == (pct_change > 0)


def _corr(xs: list[float], ys: list[float]) -> Optional[dict[str, Any]]:
    """Legacy pooled Pearson (n>=3). Kept for OLD / production field parity."""
    if len(xs) < 3:
        return {"r": None, "p_value": None, "n": len(xs)}
    if np.std(xs) == 0 or np.std(ys) == 0:
        return {"r": None, "p_value": None, "n": len(xs)}
    r, p = pearsonr(xs, ys)
    return {"r": float(r), "p_value": float(p), "n": len(xs)}


def summarize(filings: list[dict[str, Any]]) -> dict[str, Any]:
    """Legacy pooled summary (10-K + 10-Q mixed). Does not mutate filings."""
    income_pairs: list[tuple[float, float]] = []
    revenue_pairs: list[tuple[float, float]] = []
    income_agree: list[bool] = []
    revenue_agree: list[bool] = []

    for f in filings:
        score = _sentiment_score(f)
        if score is None:
            continue
        metrics = f.get("metrics") or {}
        ni = (metrics.get("net_income") or {}).get("pct_change")
        if ni is None:
            ni = f.get("income_pct")
        rev = (metrics.get("revenue") or {}).get("pct_change")
        if rev is None:
            rev = f.get("revenue_pct")
        if ni is not None:
            income_pairs.append((score, float(ni)))
        if rev is not None:
            revenue_pairs.append((score, float(rev)))
        agr = f.get("agreement") or {}
        if agr.get("net_income") is not None:
            income_agree.append(bool(agr["net_income"]))
        if agr.get("revenue") is not None:
            revenue_agree.append(bool(agr["revenue"]))

    def rate(vals: list[bool]) -> Optional[float]:
        if not vals:
            return None
        return sum(vals) / len(vals)

    return {
        "correlation": {
            "net_income": _corr([a for a, _ in income_pairs], [b for _, b in income_pairs]),
            "revenue": _corr([a for a, _ in revenue_pairs], [b for _, b in revenue_pairs]),
        },
        "agreement_rate": {
            "net_income": rate(income_agree),
            "revenue": rate(revenue_agree),
        },
        "analyzed_count": sum(1 for f in filings if _sentiment_score(f) is not None),
    }


def _sentiment_score(f: dict[str, Any]) -> Optional[float]:
    sent = f.get("sentiment")
    if isinstance(sent, dict):
        score = sent.get("score")
        return None if score is None else float(score)
    if isinstance(sent, (int, float)):
        return float(sent)
    return None


def extract_metric_pairs(
    filings: list[dict[str, Any]],
    metric_key: str,
    *,
    form_filter: Optional[str] = None,
) -> tuple[list[float], list[float]]:
    """Extract (sentiment, YoY) pairs without mutating source filings."""
    xs: list[float] = []
    ys: list[float] = []
    for f in filings:
        bucket = form_bucket(f.get("form"))
        if form_filter == FORM_10Q and bucket != FORM_10Q:
            continue
        if form_filter == FORM_10K and bucket != FORM_10K:
            continue
        score = _sentiment_score(f)
        metrics = f.get("metrics") or {}
        if metric_key == "net_income":
            y = (metrics.get("net_income") or {}).get("pct_change")
            if y is None:
                y = f.get("income_pct")
        else:
            y = (metrics.get("revenue") or {}).get("pct_change")
            if y is None:
                y = f.get("revenue_pct")
        if score is None or y is None:
            continue
        xs.append(float(score))
        ys.append(float(y))
    return xs, ys


def summarize_phase2(filings: list[dict[str, Any]]) -> dict[str, Any]:
    """Form-separated contemporaneous associations (Phase 2).

    Raw filing observations are never modified.
    Combined (pooled) results are labeled exploratory only.
    """
    scopes = (
        (FORM_10Q, FORM_10Q),
        (FORM_10K, FORM_10K),
        (FORM_COMBINED, None),
    )
    by_form: dict[str, Any] = {}
    for label, filt in scopes:
        income_x, income_y = extract_metric_pairs(filings, "net_income", form_filter=filt)
        rev_x, rev_y = extract_metric_pairs(filings, "revenue", form_filter=filt)
        by_form[label] = {
            "form_type": label,
            "exploratory": label == FORM_COMBINED,
            "net_income": analyze_pairs(income_x, income_y, form_type=label, metric="net_income"),
            "revenue": analyze_pairs(rev_x, rev_y, form_type=label, metric="revenue"),
        }

    return {
        "association_kind": "contemporaneous_same_filing",
        "min_n_correlation": MIN_N_CORRELATION,
        "analyzed_count": sum(1 for f in filings if _sentiment_score(f) is not None),
        "by_form": by_form,
        "primary": {
            "10-Q": by_form[FORM_10Q],
            "10-K": by_form[FORM_10K],
        },
        "exploratory_combined": by_form[FORM_COMBINED],
        "legacy_pooled": summarize(filings),
    }


def agreement_sensitivity(
    filings: list[dict[str, Any]],
    metric_key: str,
    *,
    form_filter: Optional[str] = None,
    sentiment_thresholds: tuple[float, ...] = (0.02, 0.05, 0.10),
    yoy_thresholds: tuple[float, ...] = (0.005, 0.01, 0.02),
) -> list[dict[str, Any]]:
    """Sensitivity grid for agreement thresholds (diagnostic; production stays 0.05 / 1%)."""
    xs, ys = extract_metric_pairs(filings, metric_key, form_filter=form_filter)
    rows: list[dict[str, Any]] = []
    for s_thr in sentiment_thresholds:
        for y_thr in yoy_thresholds:
            counts = agreement_counts(xs, ys, sentiment_neutral=s_thr, yoy_neutral=y_thr)
            rows.append(
                {
                    "sentiment_neutral": s_thr,
                    "yoy_neutral": y_thr,
                    "is_production": s_thr == NEUTRAL_SENTIMENT and y_thr == NEUTRAL_YOY,
                    **counts,
                }
            )
    return rows
