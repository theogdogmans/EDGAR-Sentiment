"""Phase 2 statistical primitives for contemporaneous MD&A–financial associations.

Terminology deliberately avoids predictive / causal / trading language.
These statistics measure whether management tone in a filing moves with the
financial performance discussed in that same filing.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

import numpy as np
from scipy.stats import pearsonr, spearmanr


# --- Sample-size policy -------------------------------------------------------
# Correlations below this are not treated as meaningful company results.
MIN_N_CORRELATION = 4
# Rankings eligibility (primary production rule once Phase 3 adopts it).
MIN_N_RANKING = 6
# Alternative ranking threshold evaluated in audits (more defensible).
MIN_N_RANKING_STRICT = 8
# Fisher CI requires n - 3 > 0.
MIN_N_FISHER_CI = 4
# Winsorization at company-level P1/P99 is unstable when n is small: the 1st
# percentile is essentially the sample minimum. Require enough points that
# order statistics are not pure extremes.
MIN_N_WINSOR = 20

NEUTRAL_SENTIMENT = 0.05
NEUTRAL_YOY = 0.01  # 1%

FORM_10Q = "10-Q"
FORM_10K = "10-K"
FORM_COMBINED = "combined"  # exploratory pooled label only

RELIABILITY_INSUFFICIENT = "insufficient_observations"
RELIABILITY_VERY_LIMITED = "very_limited_sample"
RELIABILITY_LIMITED = "limited_sample"
RELIABILITY_MORE_ESTABLISHED = "more_established_sample"


def reliability_class(n: int) -> str:
    if n < 4:
        return RELIABILITY_INSUFFICIENT
    if n <= 5:
        return RELIABILITY_VERY_LIMITED
    if n <= 9:
        return RELIABILITY_LIMITED
    return RELIABILITY_MORE_ESTABLISHED


def ranking_eligible(n: int, *, threshold: int = MIN_N_RANKING) -> bool:
    return n >= threshold


def form_bucket(form: Optional[str]) -> Optional[str]:
    if not form:
        return None
    f = str(form).upper()
    if f.startswith("10-Q"):
        return FORM_10Q
    if f.startswith("10-K"):
        return FORM_10K
    return None


def _as_arrays(xs: Sequence[float], ys: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    return x, y


def empty_pearson(n: int = 0) -> dict[str, Any]:
    return {
        "r": None,
        "n": int(n),
        "p_value": None,
        "ci_low": None,
        "ci_high": None,
        "method": "pearson_fisher_ci",
        "status": "insufficient_n" if n < MIN_N_CORRELATION else "undefined",
    }


def empty_spearman(n: int = 0) -> dict[str, Any]:
    return {
        "rho": None,
        "n": int(n),
        "p_value": None,
        "method": "spearman",
        "status": "insufficient_n" if n < MIN_N_CORRELATION else "undefined",
    }


def fisher_ci(r: float, n: int, alpha: float = 0.05) -> tuple[Optional[float], Optional[float]]:
    """95% CI for Pearson r via Fisher z-transformation. Requires n >= 4."""
    if n < MIN_N_FISHER_CI or r is None or not np.isfinite(r):
        return None, None
    # Clamp for numerical stability at |r| == 1
    r_clip = float(np.clip(r, -0.999999, 0.999999))
    z = np.arctanh(r_clip)
    se = 1.0 / np.sqrt(n - 3)
    # Normal critical value for 95%
    z_crit = 1.959963984540054
    lo = np.tanh(z - z_crit * se)
    hi = np.tanh(z + z_crit * se)
    return float(lo), float(hi)


def pearson_association(xs: Sequence[float], ys: Sequence[float]) -> dict[str, Any]:
    """Contemporaneous Pearson association with Fisher CI when valid."""
    n = len(xs)
    if n != len(ys):
        raise ValueError("xs and ys must have equal length")
    if n < MIN_N_CORRELATION:
        return empty_pearson(n)
    x, y = _as_arrays(xs, ys)
    if np.std(x, ddof=0) == 0 or np.std(y, ddof=0) == 0:
        out = empty_pearson(n)
        out["status"] = "zero_variance"
        return out
    r, p = pearsonr(x, y)
    if not np.isfinite(r) or not np.isfinite(p):
        out = empty_pearson(n)
        out["status"] = "undefined"
        return out
    ci_low, ci_high = fisher_ci(float(r), n)
    return {
        "r": float(r),
        "n": n,
        "p_value": float(p),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "method": "pearson_fisher_ci",
        "status": "ok",
    }


def spearman_association(xs: Sequence[float], ys: Sequence[float]) -> dict[str, Any]:
    """Contemporaneous Spearman rank association."""
    n = len(xs)
    if n != len(ys):
        raise ValueError("xs and ys must have equal length")
    if n < MIN_N_CORRELATION:
        return empty_spearman(n)
    x, y = _as_arrays(xs, ys)
    if np.std(x, ddof=0) == 0 or np.std(y, ddof=0) == 0:
        out = empty_spearman(n)
        out["status"] = "zero_variance"
        return out
    rho, p = spearmanr(x, y)
    if not np.isfinite(rho) or not np.isfinite(p):
        out = empty_spearman(n)
        out["status"] = "undefined"
        return out
    return {
        "rho": float(rho),
        "n": n,
        "p_value": float(p),
        "method": "spearman",
        "status": "ok",
    }


def winsorize_values(values: Sequence[float], lower_pct: float = 1.0, upper_pct: float = 99.0) -> list[float]:
    """Return a new list; does not mutate the input sequence."""
    arr = np.asarray(list(values), dtype=float)
    lo = float(np.percentile(arr, lower_pct))
    hi = float(np.percentile(arr, upper_pct))
    return [float(np.clip(v, lo, hi)) for v in arr]


def pearson_winsorized_y(
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    min_n: int = MIN_N_WINSOR,
    lower_pct: float = 1.0,
    upper_pct: float = 99.0,
) -> dict[str, Any]:
    """Pearson on sentiment (raw) vs YoY winsorized at group P1/P99.

    Returns null when n < min_n rather than inventing unstable percentiles.
    Never mutates xs/ys.
    """
    n = len(xs)
    base = {
        "r": None,
        "n": n,
        "p_value": None,
        "ci_low": None,
        "ci_high": None,
        "method": "pearson_winsorized_y_p1_p99",
        "winsor_lower": None,
        "winsor_upper": None,
        "min_n_required": min_n,
        "status": "insufficient_n_for_winsor",
    }
    if n < min_n or n != len(ys):
        return base
    arr = np.asarray(list(ys), dtype=float)
    lo = float(np.percentile(arr, lower_pct))
    hi = float(np.percentile(arr, upper_pct))
    y_w = [float(np.clip(v, lo, hi)) for v in arr]
    out = pearson_association(xs, y_w)
    out["method"] = "pearson_winsorized_y_p1_p99"
    out["winsor_lower"] = lo
    out["winsor_upper"] = hi
    out["min_n_required"] = min_n
    return out


def agreement_counts(
    sentiments: Sequence[float],
    yoy_values: Sequence[float],
    *,
    sentiment_neutral: float = NEUTRAL_SENTIMENT,
    yoy_neutral: float = NEUTRAL_YOY,
) -> dict[str, Any]:
    """Direction agreement with explicit numerator/denominator.

    Agreement: same sign after excluding near-neutral tone and near-flat YoY.
    """
    if len(sentiments) != len(yoy_values):
        raise ValueError("length mismatch")
    num = 0
    den = 0
    for s, y in zip(sentiments, yoy_values):
        if abs(s) < sentiment_neutral or abs(y) < yoy_neutral:
            continue
        den += 1
        if (s > 0) == (y > 0):
            num += 1
    return {
        "agree": num,
        "eligible": den,
        "rate": (num / den) if den else None,
        "sentiment_neutral": sentiment_neutral,
        "yoy_neutral": yoy_neutral,
        "label": f"{num} / {den}" if den else None,
    }


def benjamini_hochberg(p_values: Sequence[Optional[float]]) -> list[Optional[float]]:
    """Return FDR q-values aligned to input order. None inputs stay None."""
    indexed: list[tuple[int, float]] = []
    for i, p in enumerate(p_values):
        if p is None or not np.isfinite(p):
            continue
        indexed.append((i, float(p)))
    m = len(indexed)
    out: list[Optional[float]] = [None] * len(p_values)
    if m == 0:
        return out
    indexed.sort(key=lambda t: t[1])
    prev_q = 1.0
    q_by_rank: list[tuple[int, float]] = []
    for rank_desc, (idx, p) in enumerate(reversed(indexed), start=0):
        # ranks from m down to 1
        rank = m - rank_desc
        q = min(prev_q, p * m / rank)
        prev_q = q
        q_by_rank.append((idx, float(min(q, 1.0))))
    for idx, q in q_by_rank:
        out[idx] = q
    return out


def distribution_summary(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std": None,
            "p1": None,
            "p5": None,
            "p25": None,
            "p75": None,
            "p95": None,
            "p99": None,
        }
    arr = np.asarray(list(values), dtype=float)
    pcts = np.percentile(arr, [1, 5, 25, 50, 75, 95, 99])
    return {
        "n": int(arr.size),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "median": float(pcts[3]),
        "std": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        "p1": float(pcts[0]),
        "p5": float(pcts[1]),
        "p25": float(pcts[2]),
        "p75": float(pcts[4]),
        "p95": float(pcts[5]),
        "p99": float(pcts[6]),
    }


def flag_ni_outlier(
    *,
    current: Optional[float],
    prior: Optional[float],
    yoy: Optional[float],
) -> list[str]:
    """Heuristic flags; does not delete observations."""
    flags: list[str] = []
    if prior is not None and abs(prior) > 0 and abs(prior) < 1e6:  # absolute dollars heuristic
        # Near-zero prior in accounting sense: |prior| tiny relative to |current|
        if current is not None and abs(prior) < max(1.0, 0.01 * abs(current)):
            flags.append("near_zero_prior_income")
        elif abs(prior) < 1_000_000 and yoy is not None and abs(yoy) > 2.0:
            flags.append("near_zero_prior_income")
    if current is not None and prior is not None:
        if prior < 0 and current > 0:
            flags.append("loss_to_profit")
        if prior > 0 and current < 0:
            flags.append("profit_to_loss")
    if yoy is not None and abs(yoy) > 5.0 and "near_zero_prior_income" not in flags:
        flags.append("extreme_yoy_magnitude")
    return flags


def fisher_mean_r(rs: Iterable[float], ns: Optional[Iterable[int]] = None) -> Optional[float]:
    """Equal-weight Fisher-z mean of Pearson r values (company-balanced sector)."""
    vals = [float(r) for r in rs if r is not None and np.isfinite(r)]
    if not vals:
        return None
    zs = [np.arctanh(np.clip(r, -0.999999, 0.999999)) for r in vals]
    return float(np.tanh(np.mean(zs)))


def analyze_pairs(
    sentiments: Sequence[float],
    yoy_values: Sequence[float],
    *,
    form_type: str,
    metric: str,
    winsor_min_n: int = MIN_N_WINSOR,
) -> dict[str, Any]:
    """Full contemporaneous association bundle for one form × metric group."""
    xs = list(sentiments)
    ys = list(yoy_values)
    n = len(xs)
    raw = pearson_association(xs, ys)
    spear = spearman_association(xs, ys)
    wins = pearson_winsorized_y(xs, ys, min_n=winsor_min_n)
    agree = agreement_counts(xs, ys)
    return {
        "form_type": form_type,
        "metric": metric,
        "association_kind": "contemporaneous_same_filing",
        "n": n,
        "reliability": reliability_class(n),
        "ranking_eligible": ranking_eligible(n),
        "ranking_eligible_strict_n8": ranking_eligible(n, threshold=MIN_N_RANKING_STRICT),
        "raw_pearson": raw,
        "winsorized_pearson": wins,
        "spearman": spear,
        "agreement": agree,
        # Convenience mirrors for audits / JSON consumers
        "raw_pearson_r": raw.get("r"),
        "winsorized_pearson_r": wins.get("r"),
        "spearman_rho": spear.get("rho"),
        "p_value": raw.get("p_value"),
        "ci_low": raw.get("ci_low"),
        "ci_high": raw.get("ci_high"),
    }
