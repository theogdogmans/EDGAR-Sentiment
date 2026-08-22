#!/usr/bin/env python3
"""Phase 4 final research report from the completed Phase 3 corpus.

Does not publish to Supabase. Does not mutate raw YoY observations.
Reads local Phase 3 SQLite (PHASE3_DB_NAME) after Phase 2 recompute.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("PHASE3_DB_NAME", "edgar_phase3.db")

from app import db  # noqa: E402
from app.compare.rollup import (  # noqa: E402
    build_company_stats,
    build_sector_stats,
    ranking_eligibility_counts,
)
from app.compare.stats_core import (  # noqa: E402
    FORM_10K,
    FORM_10Q,
    FORM_COMBINED,
    distribution_summary,
    flag_ni_outlier,
    form_bucket,
)
from app.phase3_rebuild import registrant_plan, sector_revenue_block_stats  # noqa: E402

FOCUS = ["AAPL", "ADI", "ABBV", "ADSK", "AFL", "AES", "AMZN", "MSFT", "ADM", "NVDA"]
OUT_DIR = ROOT / "backend" / "data" / "phase4"
THRESHOLDS = (6, 8, 10, 12)

_COMPANY_SYNC_KEYS = (
    "ticker",
    "display",
    "name",
    "sector",
    "cik",
    "n_filings",
    "mean_sentiment",
    "r_income",
    "p_income",
    "n_income",
    "r_revenue",
    "p_revenue",
    "n_revenue",
    "agreement_income",
    "agreement_revenue",
    "points",
    "featured",
)
_SECTOR_SYNC_KEYS = (
    "sector",
    "n_companies",
    "n_filings",
    "mean_sentiment",
    "r_income",
    "p_income",
    "n_income",
    "r_revenue",
    "p_revenue",
    "n_revenue",
    "agreement_income",
    "agreement_revenue",
    "points",
)


def _production_company_row(row: dict[str, Any]) -> dict[str, Any]:
    """Legacy production sync shape with compact chart points (no sentences)."""
    out = {k: row[k] for k in _COMPANY_SYNC_KEYS if k in row}
    slim_points = []
    for p in out.get("points") or []:
        slim_points.append(
            {
                "accession": p.get("accession"),
                "form": p.get("form"),
                "filed": p.get("filed"),
                "sentiment": p.get("sentiment"),
                "income_pct": p.get("income_pct"),
                "revenue_pct": p.get("revenue_pct"),
            }
        )
    out["points"] = slim_points
    return out


def _production_sector_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in _SECTOR_SYNC_KEYS if k in row}


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "null"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def _assoc(c: dict[str, Any], form: str = FORM_10Q, metric: str = "net_income") -> dict[str, Any]:
    return (((c.get("stats_phase2") or {}).get("by_form") or {}).get(form) or {}).get(metric) or {}


def _row_summary(c: dict[str, Any], form: str = FORM_10Q, metric: str = "net_income") -> dict[str, Any]:
    a = _assoc(c, form, metric)
    raw = a.get("raw_pearson") or {}
    spear = a.get("spearman") or {}
    agree = a.get("agreement") or {}
    wins = a.get("winsorized_pearson") or {}
    return {
        "ticker": c["ticker"],
        "company": c.get("name"),
        "sector": c.get("sector"),
        "n": int(a.get("n") or 0),
        "pearson_r": raw.get("r"),
        "ci_low": raw.get("ci_low"),
        "ci_high": raw.get("ci_high"),
        "p": raw.get("p_value"),
        "q": a.get("fdr_q_value"),
        "spearman_rho": spear.get("rho"),
        "spearman_p": spear.get("p_value"),
        "agree_num": agree.get("agree"),
        "agree_den": agree.get("eligible"),
        "agree_label": agree.get("label"),
        "agree_rate": agree.get("rate"),
        "reliability": a.get("reliability"),
        "winsor_r": wins.get("r"),
        "winsor_n": wins.get("n"),
    }


def _eligible_rows(companies: list[dict[str, Any]], min_n: int) -> list[dict[str, Any]]:
    out = []
    for c in companies:
        s = _row_summary(c, FORM_10Q, "net_income")
        if s["n"] >= min_n and s["pearson_r"] is not None:
            out.append(s)
    return out


def _same_sign(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return False
    if a == 0 or b == 0:
        return a == b
    return (a > 0) == (b > 0)


def _eligibility_extended(companies: list[dict[str, Any]]) -> dict[str, int]:
    base = ranking_eligibility_counts(companies, form=FORM_10Q, metric="net_income")
    n12 = 0
    for c in companies:
        n = int(_assoc(c, FORM_10Q, "net_income").get("n") or 0)
        if n >= 12:
            n12 += 1
    base["n_ge_12"] = n12
    return base


def _fdr_section(companies: list[dict[str, Any]], min_n: int = 6) -> dict[str, Any]:
    rows = _eligible_rows(companies, min_n)
    p05 = [r for r in rows if r["p"] is not None and float(r["p"]) < 0.05]
    q05 = [r for r in rows if r["q"] is not None and float(r["q"]) < 0.05]
    q01 = [r for r in rows if r["q"] is not None and float(r["q"]) < 0.01]
    survivors = sorted(q05, key=lambda x: float(x["q"]))
    return {
        "min_n": min_n,
        "ranking_eligible": len(rows),
        "raw_p_lt_05": len(p05),
        "fdr_q_lt_05": len(q05),
        "fdr_q_lt_01": len(q01),
        "fdr_survivors": survivors,
    }


def _robust_tables(companies: list[dict[str, Any]]) -> dict[str, Any]:
    n8 = _eligible_rows(companies, 8)

    robust = [
        r
        for r in n8
        if r["spearman_rho"] is not None
        and _same_sign(r["pearson_r"], r["spearman_rho"])
        and abs(float(r["pearson_r"]) - float(r["spearman_rho"])) <= 0.25
    ]
    pos = sorted(
        [r for r in robust if float(r["pearson_r"]) > 0],
        key=lambda x: min(float(x["pearson_r"]), float(x["spearman_rho"])),
        reverse=True,
    )[:15]
    neg = sorted(
        [r for r in robust if float(r["pearson_r"]) < 0],
        key=lambda x: max(float(x["pearson_r"]), float(x["spearman_rho"])),
    )[:15]
    agree_hi = sorted(
        [r for r in n8 if r.get("agree_rate") is not None and (r.get("agree_den") or 0) >= 5],
        key=lambda x: float(x["agree_rate"]),
        reverse=True,
    )[:15]
    disagree = sorted(
        [r for r in n8 if r["spearman_rho"] is not None],
        key=lambda x: abs(float(x["pearson_r"]) - float(x["spearman_rho"])),
        reverse=True,
    )[:15]

    # Sector raw vs winsorized filing-weighted differences (10-Q NI)
    sector_diffs = []
    # filled later when sectors available

    strong_fail_fdr = sorted(
        [
            r
            for r in n8
            if r["pearson_r"] is not None
            and abs(float(r["pearson_r"])) >= 0.45
            and r["p"] is not None
            and float(r["p"]) < 0.05
            and (r["q"] is None or float(r["q"]) >= 0.05)
        ],
        key=lambda x: abs(float(x["pearson_r"])),
        reverse=True,
    )[:15]

    weak_strong_agree = sorted(
        [
            r
            for r in n8
            if r["pearson_r"] is not None
            and abs(float(r["pearson_r"])) < 0.25
            and r.get("agree_rate") is not None
            and float(r["agree_rate"]) >= 0.70
            and (r.get("agree_den") or 0) >= 5
        ],
        key=lambda x: float(x["agree_rate"]),
        reverse=True,
    )[:15]

    return {
        "A_strongest_positive_robust_n8": pos,
        "B_strongest_negative_robust_n8": neg,
        "C_highest_direction_agreement_n8": agree_hi,
        "D_largest_pearson_spearman_gap_n8": disagree,
        "E_sector_raw_vs_winsor": sector_diffs,  # filled below
        "F_strong_pearson_fail_fdr_n8": strong_fail_fdr,
        "G_weak_pearson_strong_agreement_n8": weak_strong_agree,
    }


def _sector_section(sectors: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    material = []
    for s in sectors:
        block = (((s.get("stats_phase2") or {}).get("by_form") or {}).get(FORM_10Q) or {}).get(
            "net_income"
        ) or {}
        fw = block.get("filing_weighted") or {}
        cb = block.get("company_balanced") or {}
        fw_raw = fw.get("raw_pearson") or {}
        fw_sp = fw.get("spearman") or {}
        fw_w = fw.get("winsorized_pearson") or {}
        fw_ag = block.get("filing_weighted_agreement") or {}
        cb_ag = block.get("company_balanced_agreement") or {}
        fw_r = fw_raw.get("r")
        cb_r = cb.get("r")
        row = {
            "sector": s["sector"],
            "n_companies": s.get("n_companies"),
            "n_filings": s.get("n_filings"),
            "filing_weighted": {
                "n": fw.get("n"),
                "pearson_r": fw_r,
                "p": fw_raw.get("p_value"),
                "spearman_rho": fw_sp.get("rho"),
                "spearman_p": fw_sp.get("p_value"),
                "winsor_r": fw_w.get("r") if int(fw.get("n") or 0) >= 20 else None,
                "agreement": fw_ag.get("label"),
                "agree_rate": fw_ag.get("rate"),
            },
            "company_balanced": {
                "r": cb_r,
                "n_companies": cb.get("n_companies"),
                "agreement_rate": cb_ag.get("rate"),
            },
        }
        rows.append(row)
        if fw_r is not None and cb_r is not None:
            delta = float(cb_r) - float(fw_r)
            sign_flip = (float(fw_r) > 0) != (float(cb_r) > 0) and abs(float(fw_r)) > 0.05 and abs(
                float(cb_r)
            ) > 0.05
            if abs(delta) >= 0.15 or sign_flip:
                material.append(
                    {
                        "sector": s["sector"],
                        "filing_weighted_r": fw_r,
                        "company_balanced_r": cb_r,
                        "delta": delta,
                        "sign_flip": sign_flip,
                    }
                )
    return {"sectors_10q_ni": rows, "material_weighting_changes": material}


def _coverage_report(companies: list[dict[str, Any]]) -> dict[str, Any]:
    by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in companies:
        by_sector[c.get("sector") or "Unknown"].append(c)

    sector_rows = []
    for sector, members in sorted(by_sector.items()):
        scored = [c for c in members if int(c.get("n_filings") or 0) > 0]
        def n_ge(thr: int) -> int:
            return sum(1 for c in members if int(_assoc(c, FORM_10Q, "net_income").get("n") or 0) >= thr)

        rev_ok = sum(1 for c in members if int(_assoc(c, FORM_10Q, "revenue").get("n") or 0) >= 1)
        ni_ok = sum(1 for c in members if int(_assoc(c, FORM_10Q, "net_income").get("n") or 0) >= 1)
        sector_rows.append(
            {
                "sector": sector,
                "companies_in_universe": len(members),
                "with_scored_filing": len(scored),
                "n_ge_6": n_ge(6),
                "n_ge_8": n_ge(8),
                "n_ge_10": n_ge(10),
                "with_valid_revenue_10q": rev_ok,
                "with_valid_ni_10q": ni_ok,
            }
        )

    logs = [dict(r) for r in db.list_quality_logs()]
    fail_reasons: Counter[str] = Counter()
    for lg in logs:
        fr = lg.get("failure_reason") or ("ok" if lg.get("sentiment_score") is not None else "unknown")
        key = str(fr).split(";")[0][:120]
        fail_reasons[key] = fail_reasons.get(key, 0) + 1

    q = db.quality_log_counts()
    mda_ok = sum(1 for lg in logs if lg.get("extraction_ok"))
    rev_block = sector_revenue_block_stats()

    return {
        "by_sector": sector_rows,
        "totals": {
            **q,
            "mda_extractions_ok": mda_ok,
            "quality_log_rows": len(logs),
            "coverage": db.coverage(),
            "revenue_block": rev_block,
            "top_failure_reasons": dict(fail_reasons.most_common(25)),
        },
    }


def _outlier_audit(companies: list[dict[str, Any]]) -> dict[str, Any]:
    obs: list[dict[str, Any]] = []
    ni_q: list[float] = []
    ni_k: list[float] = []
    for c in companies:
        for p in c.get("points") or []:
            yoy = p.get("income_pct")
            if yoy is None or p.get("sentiment") is None:
                continue
            bucket = form_bucket(p.get("form"))
            y = float(yoy)
            if bucket == FORM_10Q:
                ni_q.append(y)
            elif bucket == FORM_10K:
                ni_k.append(y)
            cur = p.get("income_current")
            prior = p.get("income_prior")
            flags = flag_ni_outlier(
                current=float(cur) if cur is not None else None,
                prior=float(prior) if prior is not None else None,
                yoy=y,
            )
            cause = "other"
            if "near_zero_prior_income" in flags:
                cause = "near_zero_prior"
            elif "loss_to_profit" in flags:
                cause = "loss_to_profit"
            elif "profit_to_loss" in flags:
                cause = "profit_to_loss"
            obs.append(
                {
                    "ticker": c["ticker"],
                    "form": p.get("form"),
                    "report_date": p.get("report_date") or p.get("filed"),
                    "current_ni": cur,
                    "prior_ni": prior,
                    "yoy": y,
                    "sentiment": p.get("sentiment"),
                    "cause": cause,
                    "flags": flags,
                }
            )
    extreme = sorted(obs, key=lambda x: abs(float(x["yoy"])), reverse=True)[:25]
    return {
        "ni_yoy_dist_10q": distribution_summary(ni_q),
        "ni_yoy_dist_10k": distribution_summary(ni_k),
        "top_25_extreme_ni_yoy": extreme,
    }


def _case_studies(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by = {c["ticker"]: c for c in companies}
    out = []
    for t in FOCUS:
        c = by.get(t)
        if not c:
            out.append({"ticker": t, "missing": True})
            continue
        ni = _row_summary(c, FORM_10Q, "net_income")
        rev = _row_summary(c, FORM_10Q, "revenue")
        out.append(
            {
                "ticker": t,
                "company": c.get("name"),
                "sector": c.get("sector"),
                "10q_ni": ni,
                "10q_revenue": rev,
                "10k_ni": _row_summary(c, FORM_10K, "net_income"),
                "combined_ni_exploratory": _row_summary(c, FORM_COMBINED, "net_income"),
            }
        )
    return out


def _interpret_case(row: dict[str, Any]) -> str:
    if row.get("missing"):
        return "Not present in final corpus."
    ni = row["10q_ni"]
    t = row["ticker"]
    r = ni.get("pearson_r")
    q = ni.get("q")
    p = ni.get("p")
    rho = ni.get("spearman_rho")
    n = ni.get("n")
    agree = ni.get("agree_label")
    bits = [f"10-Q NI n={n}, Pearson r={_fmt(r)}, p={_fmt(p)}, q={_fmt(q)}, Spearman ρ={_fmt(rho)}, agree={agree}."]
    if t in ("AAPL", "ADI"):
        survives = q is not None and float(q) < 0.05
        bits.append("FDR survivor." if survives else "Does not survive FDR at q<0.05.")
    if t in ("ABBV", "ADSK"):
        near_zero = r is not None and abs(float(r)) < 0.15
        bits.append("Still near zero." if near_zero else f"No longer near zero (r={_fmt(r)}).")
    if t == "AFL":
        wr = ni.get("winsor_r")
        if r is not None and wr is not None and abs(float(r) - float(wr)) >= 0.15:
            bits.append("Still outlier-sensitive (winsor shifts Pearson materially).")
        elif n is not None and n < 20:
            bits.append("Winsor not applicable at company n; check extreme YoY rows for outlier sensitivity.")
        else:
            bits.append("Outlier sensitivity less clear at full-sample company level.")
    if t == "AMZN":
        bits.append("Still negative." if r is not None and float(r) < 0 else "No longer negative.")
    if t == "MSFT":
        if r is not None and 0.2 <= float(r) <= 0.55:
            bits.append("Still moderate positive.")
        else:
            bits.append(f"Moderate-positive interpretation needs revision (r={_fmt(r)}).")
    if t == "NVDA":
        rate = ni.get("agree_rate")
        if rate is not None and float(rate) >= 0.75:
            bits.append("Still unusually high direction agreement.")
        else:
            bits.append(f"Direction agreement no longer unusually high (rate={_fmt(rate)}).")
    return " ".join(bits)


def _story(companies: list[dict[str, Any]], robust: dict[str, Any], sectors: dict[str, Any]) -> dict[str, Any]:
    n8 = _eligible_rows(companies, 8)
    pos = robust["A_strongest_positive_robust_n8"][:5]
    neg = robust["B_strongest_negative_robust_n8"][:5]
    misleading = robust["D_largest_pearson_spearman_gap_n8"][:5]
    agree = robust["C_highest_direction_agreement_n8"][:5]
    sector_findings = []
    for s in sectors["sectors_10q_ni"]:
        fw = s["filing_weighted"]
        if fw.get("n") and int(fw["n"]) >= 50 and fw.get("pearson_r") is not None:
            sector_findings.append(s)
    sector_findings = sorted(
        sector_findings, key=lambda x: abs(float(x["filing_weighted"]["pearson_r"] or 0)), reverse=True
    )[:5]

    overall = _eligible_rows(companies, 6)
    median_abs_r = None
    if overall:
        import statistics

        median_abs_r = statistics.median([abs(float(r["pearson_r"])) for r in overall])
    fdr = _fdr_section(companies, 6)
    headline = (
        "Across the full S&P 500 Phase 3 corpus, contemporaneous MD&A tone vs NI YoY associations "
        "are mostly weak-to-modest; FDR-surviving companies are a small minority of ranking-eligible names."
        if (median_abs_r is not None and median_abs_r < 0.35) or fdr["fdr_q_lt_05"] < max(10, fdr["ranking_eligible"] // 10)
        else "A non-trivial set of companies shows stronger contemporaneous associations after multiple-comparison control."
    )
    return {
        "headline": headline,
        "median_abs_pearson_r_n6": median_abs_r,
        "positive_examples": pos,
        "negative_examples": neg,
        "pearson_misleading": misleading,
        "high_agreement": agree,
        "sector_examples": sector_findings,
    }


def _supabase_footprint(companies: list[dict[str, Any]], sectors: list[dict[str, Any]]) -> dict[str, Any]:
    prod_c = [_production_company_row(c) for c in companies]
    prod_s = [_production_sector_row(s) for s in sectors]
    c_json = json.dumps(prod_c, default=str).encode("utf-8")
    s_json = json.dumps(prod_s, default=str).encode("utf-8")
    points = sum(len(c.get("points") or []) for c in prod_c)
    sector_points = sum(len(s.get("points") or []) for s in prod_s)
    largest = max(prod_c, key=lambda r: len(json.dumps(r, default=str).encode("utf-8")))
    largest_bytes = len(json.dumps(largest, default=str).encode("utf-8"))
    # Rough Postgres estimate: JSONB ~1.5–2.5× UTF-8 JSON + indexes/toast overhead
    payload = len(c_json) + len(s_json)
    est_pg = int(payload * 2.2 + 2_000_000)  # +~2MB metadata/indexes cushion
    return {
        "company_rows": len(prod_c),
        "sector_rows": len(prod_s),
        "company_chart_points": points,
        "sector_chart_points_capped": sector_points,
        "company_json_bytes": len(c_json),
        "sector_json_bytes": len(s_json),
        "total_json_mb": round(payload / 1024 / 1024, 2),
        "estimated_postgres_mb": round(est_pg / 1024 / 1024, 2),
        "largest_company_ticker": largest.get("ticker"),
        "largest_company_row_kb": round(largest_bytes / 1024, 1),
        "safely_below_500mb": est_pg < 500 * 1024 * 1024,
        "target_band": (
            "<100 MB preferred"
            if est_pg < 100 * 1024 * 1024
            else "<200 MB acceptable"
            if est_pg < 200 * 1024 * 1024
            else ">300 MB requires redesign"
            if est_pg >= 300 * 1024 * 1024
            else "200–300 MB caution"
        ),
        "note": "Estimate for legacy production sync keys with compact points (no sentence blobs, no stats_phase2).",
    }


def _website_recs(fdr: dict[str, Any], eligibility: dict[str, int], story: dict[str, Any], case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    survivors = [r["ticker"] for r in fdr.get("fdr_survivors") or []][:5]
    cases = []
    for t in ("AAPL", "MSFT", "AMZN", "NVDA", "ADI"):
        if any(c.get("ticker") == t and not c.get("missing") for c in case_rows):
            cases.append(t)
    for t in survivors:
        if t not in cases:
            cases.append(t)
        if len(cases) >= 5:
            break
    return {
        "primary_metric": "10-Q NI should be the primary company metric (form-homogeneous, largest n).",
        "display_first": "Show Spearman alongside Pearson; lead with Spearman for robustness, keep Pearson for familiarity + CI.",
        "ranking_n": (
            "Prefer n>=8 for public rankings; keep n>=6 as exploratory/limited-sample tier."
            if eligibility.get("n_ge_8", 0) >= 100
            else "Use n>=6 with clear limited-sample labeling if n>=8 coverage is thin."
        ),
        "show_p_values": "Show p-values only with sample size and CI; never alone. Prefer FDR q for multi-company claims.",
        "fdr_badge": "Yes — badge FDR-surviving 10-Q NI results (q<0.05), with explicit multiple-comparison disclaimer.",
        "hide_10k": "Keep 10-K visible but secondary/collapsed until more annual history accumulates; do not pool as primary.",
        "revenue_secondary": "Yes — revenue secondary; exclude/label Financials & Real Estate as non-comparable.",
        "homepage_case_studies": cases[:5],
        "safest_sector_feature": (
            (story.get("sector_examples") or [{}])[0].get("sector")
            if story.get("sector_examples")
            else "Show dual weighting (filing-weighted vs company-balanced) rather than a single sector headline."
        ),
        "disclaimers": [
            "Contemporaneous same-filing association only — not prediction, forecasting, alpha, or trading advice.",
            "Tone and accounting YoY can disagree for legitimate accounting reasons (one-time items, base effects).",
            "Small n and extreme YoY can inflate Pearson; inspect Spearman, agreement, and outliers.",
            "FDR controls false discoveries across many companies; most names will not survive.",
            "Production rankings must not imply causal management-tone effects on earnings.",
        ],
    }


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = report["A_dataset_checkpoint"]
    lines += [
        "# Phase 4 — Final Full-Data Analysis",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## A. Dataset checkpoint",
        "",
        f"- Integrity: `{a['integrity']}` (backup `{a['backup_integrity']}`)",
        f"- Backup: `{a['backup_path']}` ({a['db_mb']} MB)",
        f"- Analyses: **{a['analyses']}**",
        f"- Filings attempted (quality_log): **{a['quality_attempted']}**",
        f"- Unique registrants (CIKs with filings): **{a['unique_ciks']}**",
        f"- S&P 500 ticker rows: **{a['sp500_rows']}**",
        "",
        "## B. Coverage",
        "",
        f"- Sentiment scored: {report['B_coverage']['totals'].get('sentiment_ok', report['B_coverage']['totals'])}",
        f"- Top failure reasons: see JSON",
        "",
        "## C. Ranking eligibility (10-Q NI)",
        "",
    ]
    elig = report["C_ranking_eligibility"]
    for k, v in elig.items():
        lines.append(f"- {k}: **{v}**")
    fdr = report["D_fdr_results"]
    lines += [
        "",
        "## D. FDR results (10-Q NI, ranking-eligible n≥6)",
        "",
        f"- Eligible: **{fdr['ranking_eligible']}**",
        f"- Raw p < .05: **{fdr['raw_p_lt_05']}**",
        f"- FDR q < .05: **{fdr['fdr_q_lt_05']}**",
        f"- FDR q < .01: **{fdr['fdr_q_lt_01']}**",
        "",
        "### FDR survivors (q < .05)",
        "",
    ]
    if not fdr["fdr_survivors"]:
        lines.append("_None._")
    else:
        lines.append("| ticker | company | sector | n | r | 95% CI | p | q | ρ | Spearman p | agree |")
        lines.append("|---|---|---|---:|---:|---|---:|---:|---:|---:|---|")
        for r in fdr["fdr_survivors"]:
            ci = f"[{_fmt(r['ci_low'])}, {_fmt(r['ci_high'])}]"
            lines.append(
                f"| {r['ticker']} | {r['company']} | {r['sector']} | {r['n']} | {_fmt(r['pearson_r'])} | {ci} | "
                f"{_fmt(r['p'])} | {_fmt(r['q'])} | {_fmt(r['spearman_rho'])} | {_fmt(r['spearman_p'])} | {r['agree_label']} |"
            )
    lines += ["", "## E–G. Robust / disagreements / sectors", "", "See `phase4_final_report.json` tables.", ""]
    lines += ["## I. Case studies", ""]
    for row in report["I_case_studies"]:
        lines.append(f"### {row.get('ticker')}")
        lines.append(row.get("interpretation", ""))
        lines.append("")
    story = report["J_final_conclusions"]
    lines += [
        "## J. Final conclusions",
        "",
        story["headline"],
        "",
        f"Median |Pearson r| among n≥6 eligible companies: **{_fmt(story.get('median_abs_pearson_r_n6'))}**",
        "",
        "## K. Website recommendations",
        "",
    ]
    for k, v in report["K_website_recommendations"].items():
        if isinstance(v, list):
            lines.append(f"- **{k}:**")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"- **{k}:** {v}")
    fp = report["L_supabase_footprint"]
    lines += [
        "",
        "## L. Supabase footprint estimate",
        "",
        f"- Company rows: {fp['company_rows']}",
        f"- Sector rows: {fp['sector_rows']}",
        f"- Chart points: {fp['company_chart_points']}",
        f"- JSON payload: {fp['total_json_mb']} MB",
        f"- Estimated Postgres: **{fp['estimated_postgres_mb']} MB** ({fp['target_band']})",
        f"- Largest row: {fp['largest_company_ticker']} ({fp['largest_company_row_kb']} KB)",
        f"- Below 500 MB: {fp['safely_below_500mb']}",
        "",
        "## M. Methodological limitations",
        "",
    ]
    for lim in report["M_limitations"]:
        lines.append(f"- {lim}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()

    # Checkpoint meta (already backed up externally; re-verify)
    src = ROOT / "backend" / "data" / "edgar_phase3.db"
    backup = ROOT / "backend" / "data" / "final" / "edgar_phase3_final.db"
    import sqlite3

    c = sqlite3.connect(str(src))
    integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
    analyses = c.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    quality_attempted = c.execute("SELECT COUNT(*) FROM quality_log").fetchone()[0]
    unique_ciks = c.execute("SELECT COUNT(DISTINCT cik) FROM filings").fetchone()[0]
    sp500_rows = c.execute("SELECT COUNT(*) FROM sp500").fetchone()[0]
    c.close()
    b_integrity = None
    if backup.exists():
        b = sqlite3.connect(str(backup))
        b_integrity = b.execute("PRAGMA integrity_check").fetchone()[0]
        b.close()

    companies = build_company_stats()
    plan = registrant_plan()
    alias_set = {a for item in plan for a in item.get("alias_tickers") or []}
    for row in companies:
        if row["ticker"] in alias_set:
            row["exclude_from_sector"] = True
    sector_input = [c for c in companies if not c.get("exclude_from_sector")]
    sectors = build_sector_stats(sector_input)

    # Persist Phase 2 tables if empty / refresh
    ts = datetime.now(timezone.utc).isoformat()
    db.save_phase2_company_stats(companies, ts)
    db.save_phase2_sector_stats(sectors, ts)

    eligibility = _eligibility_extended(companies)
    fdr = _fdr_section(companies, 6)
    robust = _robust_tables(companies)
    sector_sec = _sector_section(sectors)
    # Fill E: largest raw vs winsor sector differences
    e_rows = []
    for s in sector_sec["sectors_10q_ni"]:
        fw = s["filing_weighted"]
        if fw.get("pearson_r") is not None and fw.get("winsor_r") is not None:
            e_rows.append(
                {
                    "sector": s["sector"],
                    "raw_r": fw["pearson_r"],
                    "winsor_r": fw["winsor_r"],
                    "abs_delta": abs(float(fw["pearson_r"]) - float(fw["winsor_r"])),
                    "n": fw.get("n"),
                }
            )
    robust["E_sector_raw_vs_winsor"] = sorted(e_rows, key=lambda x: x["abs_delta"], reverse=True)[:15]

    coverage = _coverage_report(companies)
    outliers = _outlier_audit(companies)
    cases = _case_studies(companies)
    for row in cases:
        row["interpretation"] = _interpret_case(row)
    story = _story(companies, robust, sector_sec)
    footprint = _supabase_footprint(companies, sectors)
    website = _website_recs(fdr, eligibility, story, cases)

    threshold_counts = {f"n_ge_{t}": sum(1 for c in companies if int(_assoc(c).get("n") or 0) >= t) for t in THRESHOLDS}

    report = {
        "generated_at": ts,
        "A_dataset_checkpoint": {
            "integrity": integrity,
            "backup_integrity": b_integrity,
            "backup_path": str(backup),
            "db_bytes": backup.stat().st_size if backup.exists() else src.stat().st_size,
            "db_mb": round((backup.stat().st_size if backup.exists() else src.stat().st_size) / 1024 / 1024, 2),
            "analyses": analyses,
            "quality_attempted": quality_attempted,
            "unique_ciks": unique_ciks,
            "sp500_rows": sp500_rows,
            "companies_built": len(companies),
            "sectors_built": len(sectors),
        },
        "B_coverage": coverage,
        "C_ranking_eligibility": {**eligibility, **threshold_counts},
        "D_fdr_results": fdr,
        "E_robust_company_relationships": {
            "positive": robust["A_strongest_positive_robust_n8"],
            "negative": robust["B_strongest_negative_robust_n8"],
            "high_agreement": robust["C_highest_direction_agreement_n8"],
        },
        "F_pearson_spearman_disagreements": robust["D_largest_pearson_spearman_gap_n8"],
        "F_strong_fail_fdr": robust["F_strong_pearson_fail_fdr_n8"],
        "F_weak_pearson_strong_agree": robust["G_weak_pearson_strong_agreement_n8"],
        "G_sector_findings": sector_sec,
        "G_sector_raw_vs_winsor": robust["E_sector_raw_vs_winsor"],
        "H_outlier_audit": outliers,
        "I_case_studies": cases,
        "J_final_conclusions": story,
        "K_website_recommendations": website,
        "L_supabase_footprint": footprint,
        "M_limitations": [
            "Associations are contemporaneous within the same filing; they are not predictive.",
            "NI YoY base effects (near-zero priors, loss↔profit flips) can dominate Pearson.",
            "10-K samples remain short for many registrants; combined pooling mixes form dynamics.",
            "FDR is applied across ranking-eligible companies; it does not make individual r causal.",
            "Financials/Real Estate revenue is intentionally non-comparable and excluded from revenue rankings.",
            "MD&A extraction quality varies; residual extraction failures bias coverage by sector/ticker.",
            "Sentiment is FinBERT sentence-average tone, not a human reading of emphasis or risk language.",
            "Multiple thresholds (n=6/8/10/12) change who appears 'strong' — treat rankings as sensitivity analysis.",
        ],
    }

    json_path = OUT_DIR / "phase4_final_report.json"
    md_path = OUT_DIR / "PHASE4_FINAL_REPORT.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")

    # Compact machine tables for quick inspection
    (OUT_DIR / "fdr_survivors.json").write_text(
        json.dumps(fdr["fdr_survivors"], indent=2, default=str), encoding="utf-8"
    )
    (OUT_DIR / "checkpoint_meta.json").write_text(
        json.dumps(report["A_dataset_checkpoint"], indent=2), encoding="utf-8"
    )

    print("=" * 72)
    print("PHASE 4 FINAL REPORT")
    print("=" * 72)
    print("Checkpoint:", report["A_dataset_checkpoint"])
    print("Eligibility:", eligibility)
    print(
        f"FDR: eligible={fdr['ranking_eligible']} p<.05={fdr['raw_p_lt_05']} "
        f"q<.05={fdr['fdr_q_lt_05']} q<.01={fdr['fdr_q_lt_01']}"
    )
    print("Headline:", story["headline"])
    print("Footprint MB JSON/PG:", footprint["total_json_mb"], footprint["estimated_postgres_mb"])
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
