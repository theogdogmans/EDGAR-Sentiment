from __future__ import annotations

from typing import Any, Optional

import numpy as np
from scipy.stats import pearsonr


NEUTRAL_SENTIMENT = 0.05


def agreement(sentiment: float, pct_change: Optional[float]) -> Optional[bool]:
    if pct_change is None:
        return None
    if abs(sentiment) < NEUTRAL_SENTIMENT or abs(pct_change) < 0.01:
        return None
    return (sentiment > 0) == (pct_change > 0)


def _corr(xs: list[float], ys: list[float]) -> Optional[dict[str, Any]]:
    if len(xs) < 3:
        return {"r": None, "p_value": None, "n": len(xs)}
    if np.std(xs) == 0 or np.std(ys) == 0:
        return {"r": None, "p_value": None, "n": len(xs)}
    r, p = pearsonr(xs, ys)
    return {"r": float(r), "p_value": float(p), "n": len(xs)}


def summarize(filings: list[dict[str, Any]]) -> dict[str, Any]:
    income_pairs: list[tuple[float, float]] = []
    revenue_pairs: list[tuple[float, float]] = []
    income_agree: list[bool] = []
    revenue_agree: list[bool] = []

    for f in filings:
        sent = f.get("sentiment") or {}
        metrics = f.get("metrics") or {}
        score = sent.get("score")
        if score is None:
            continue
        ni = (metrics.get("net_income") or {}).get("pct_change")
        rev = (metrics.get("revenue") or {}).get("pct_change")
        if ni is not None:
            income_pairs.append((score, ni))
        if rev is not None:
            revenue_pairs.append((score, rev))
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
        "analyzed_count": sum(1 for f in filings if f.get("sentiment")),
    }
