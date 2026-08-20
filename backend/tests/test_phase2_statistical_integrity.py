"""Phase 2 statistical integrity tests (deterministic synthetic data)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import pearsonr, spearmanr

from app.compare.metrics import agreement, extract_metric_pairs, summarize, summarize_phase2
from app.compare.rollup import build_company_stats_from_cloud_rows, build_sector_stats
from app.compare.stats_core import (
    MIN_N_CORRELATION,
    MIN_N_WINSOR,
    agreement_counts,
    benjamini_hochberg,
    fisher_ci,
    pearson_association,
    pearson_winsorized_y,
    reliability_class,
    spearman_association,
    winsorize_values,
)


def test_pearson_correctness_matches_scipy():
    xs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    ys = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55]
    out = pearson_association(xs, ys)
    r, p = pearsonr(xs, ys)
    assert out["status"] == "ok"
    assert out["n"] == 6
    assert abs(out["r"] - float(r)) < 1e-12
    assert abs(out["p_value"] - float(p)) < 1e-12


def test_spearman_correctness_matches_scipy():
    xs = [1, 2, 3, 4, 5, 6, 7, 8]
    ys = [2, 1, 4, 3, 6, 5, 8, 7]
    out = spearman_association(xs, ys)
    rho, p = spearmanr(xs, ys)
    assert out["status"] == "ok"
    assert abs(out["rho"] - float(rho)) < 1e-12
    assert abs(out["p_value"] - float(p)) < 1e-12


def test_pvalue_and_fisher_ci_behavior():
    rng = np.random.default_rng(0)
    xs = rng.normal(size=40).tolist()
    ys = (0.8 * np.asarray(xs) + rng.normal(scale=0.2, size=40)).tolist()
    out = pearson_association(xs, ys)
    assert out["p_value"] is not None and out["p_value"] < 0.05
    assert out["ci_low"] is not None and out["ci_high"] is not None
    assert out["ci_low"] < out["r"] < out["ci_high"]
    # Near-perfect correlation: Fisher CI is finite and contains r after clip
    lo, hi = fisher_ci(0.999, 20)
    assert lo is not None and hi is not None and lo < 0.999 < hi
    lo1, hi1 = fisher_ci(1.0, 20)
    assert lo1 is not None and hi1 is not None and lo1 < hi1 <= 1.0 + 1e-9


def test_insufficient_n_returns_null_stats():
    xs = [0.1, 0.2, 0.3]
    ys = [0.2, 0.1, 0.0]
    assert len(xs) < MIN_N_CORRELATION
    p = pearson_association(xs, ys)
    s = spearman_association(xs, ys)
    assert p["r"] is None and p["p_value"] is None and p["ci_low"] is None
    assert s["rho"] is None and s["status"] == "insufficient_n"
    assert reliability_class(3) == "insufficient_observations"
    assert reliability_class(5) == "very_limited_sample"
    assert reliability_class(7) == "limited_sample"
    assert reliability_class(10) == "more_established_sample"


def test_form_separation_and_combined_exploratory():
    filings = []
    # 10-Q: strong positive association
    for i in range(8):
        filings.append(
            {
                "form": "10-Q",
                "sentiment": {"score": 0.05 * i},
                "metrics": {"net_income": {"pct_change": 0.1 * i}, "revenue": {"pct_change": 0.05 * i}},
            }
        )
    # 10-K: weak / different
    for i in range(4):
        filings.append(
            {
                "form": "10-K",
                "sentiment": {"score": 0.2 - 0.05 * i},
                "metrics": {"net_income": {"pct_change": 0.05 * i}, "revenue": {"pct_change": None}},
            }
        )
    phase2 = summarize_phase2(filings)
    q = phase2["by_form"]["10-Q"]["net_income"]
    k = phase2["by_form"]["10-K"]["net_income"]
    c = phase2["by_form"]["combined"]["net_income"]
    assert q["n"] == 8 and k["n"] == 4 and c["n"] == 12
    assert phase2["by_form"]["combined"]["exploratory"] is True
    assert phase2["by_form"]["10-Q"]["exploratory"] is False
    assert q["raw_pearson_r"] is not None
    assert k["raw_pearson_r"] is not None  # n=4 meets MIN_N_CORRELATION
    # Separation matters: combined r need not equal 10-Q r
    assert abs(q["raw_pearson_r"] - c["raw_pearson_r"]) > 1e-6 or q["n"] != c["n"]


def test_winsorization_does_not_modify_raw_observations():
    xs = list(np.linspace(0, 1, MIN_N_WINSOR))
    ys = list(np.linspace(0, 1, MIN_N_WINSOR))
    ys[0] = -50.0
    ys[-1] = 50.0
    original = list(ys)
    out = pearson_winsorized_y(xs, ys, min_n=MIN_N_WINSOR)
    assert ys == original
    assert out["r"] is not None
    assert out["winsor_lower"] is not None
    # Small-n company: winsor null
    small = pearson_winsorized_y(xs[:10], ys[:10], min_n=MIN_N_WINSOR)
    assert small["r"] is None and small["status"] == "insufficient_n_for_winsor"


def test_extreme_outlier_impact_on_raw_vs_winsor_and_spearman():
    n = 25
    xs = list(np.linspace(-0.2, 0.2, n))
    ys = [0.5 * x for x in xs]
    ys[-1] = 100.0  # extreme NI YoY
    raw = pearson_association(xs, ys)
    wins = pearson_winsorized_y(xs, ys, min_n=20)
    spear = spearman_association(xs, ys)
    assert raw["r"] is not None and wins["r"] is not None and spear["rho"] is not None
    # Outlier pulls Pearson more than Spearman / winsorized Pearson
    assert abs(raw["r"] - spear["rho"]) > 0.05 or abs(raw["r"] - wins["r"]) > 0.05


def test_agreement_numerator_denominator():
    sentiments = [0.2, 0.2, -0.2, 0.01, 0.2]
    yoys = [0.05, -0.05, -0.05, 0.05, 0.005]
    # Eligible: (0.2,0.05) agree; (0.2,-0.05) disagree; (-0.2,-0.05) agree;
    # |0.01|<0.05 neutral; |0.005|<0.01 neutral → 2/3
    out = agreement_counts(sentiments, yoys)
    assert out["agree"] == 2 and out["eligible"] == 3
    assert out["label"] == "2 / 3"
    assert abs(out["rate"] - 2 / 3) < 1e-12
    assert agreement(0.2, 0.05) is True
    assert agreement(0.01, 0.05) is None


def test_sector_filing_weighted_vs_company_balanced():
    # Company A: many filings, strong r; Company B: few filings, negative r
    cloud = [
        {
            "ticker": "AAA",
            "name": "A",
            "sector": "Tech",
            "n_filings": 8,
            "points": [
                {"form": "10-Q", "sentiment": float(i), "income_pct": float(i), "revenue_pct": float(i)}
                for i in range(8)
            ],
        },
        {
            "ticker": "BBB",
            "name": "B",
            "sector": "Tech",
            "n_filings": 6,
            "points": [
                {"form": "10-Q", "sentiment": float(i), "income_pct": float(-i), "revenue_pct": float(-i)}
                for i in range(6)
            ],
        },
    ]
    companies = build_company_stats_from_cloud_rows(cloud)
    sectors = build_sector_stats(companies)
    assert len(sectors) == 1
    block = sectors[0]["stats_phase2"]["by_form"]["10-Q"]["net_income"]
    fw = block["filing_weighted"]["raw_pearson_r"]
    cb = block["company_balanced"]["r"]
    assert fw is not None and cb is not None
    # Filing-weighted pulled toward AAA (more points); company-balanced averages both
    assert abs(fw - cb) > 1e-6
    assert block["filing_weighted_agreement"]["eligible"] >= 1


def test_fdr_benjamini_hochberg():
    p = [0.001, 0.01, 0.04, 0.20, None]
    q = benjamini_hochberg(p)
    assert q[4] is None
    assert q[0] is not None and q[0] <= q[1] <= q[2]
    assert all(qi is None or 0 <= qi <= 1 for qi in q)


def test_legacy_summarize_still_pooled():
    filings = [
        {"form": "10-Q", "sentiment": {"score": 0.1}, "metrics": {"net_income": {"pct_change": 0.2}}},
        {"form": "10-K", "sentiment": {"score": 0.2}, "metrics": {"net_income": {"pct_change": 0.3}}},
        {"form": "10-Q", "sentiment": {"score": 0.3}, "metrics": {"net_income": {"pct_change": 0.4}}},
    ]
    legacy = summarize(filings)
    assert legacy["correlation"]["net_income"]["n"] == 3


def test_winsorize_helper_is_pure():
    vals = [1.0, 2.0, 3.0, 100.0]
    copy = list(vals)
    out = winsorize_values(vals, 0, 75)
    assert vals == copy
    assert max(out) < 100.0


def test_extract_pairs_from_compact_points():
    points = [
        {"form": "10-Q", "sentiment": 0.1, "income_pct": 0.2},
        {"form": "10-K", "sentiment": 0.2, "income_pct": 0.1},
    ]
    xs, ys = extract_metric_pairs(points, "net_income", form_filter="10-Q")
    assert xs == [0.1] and ys == [0.2]
