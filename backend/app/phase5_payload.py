"""Phase 5A production sync payload builder (dry-run only).

Builds the exact company / sector / example_filings shape intended for
future Supabase upload from the completed Phase 3 corpus + Phase 2/4 stats.

Does not upload. Does not mutate raw analyses or YoY observations.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Optional

from . import db
from .compare.rollup import (
    build_company_stats,
    build_sector_stats,
    example_filing_payload,
    latest_analyzed_accession,
)
from .compare.stats_core import FORM_10K, FORM_10Q, form_bucket
from .edgar.facts import NON_COMPARABLE_REVENUE_SECTORS
from .phase3_rebuild import registrant_plan

PUBLIC_RANK_N = 8
LIMITED_RANK_N = 6
CASE_STUDY_TICKERS = ("AAPL", "ADI", "AMZN", "MSFT", "NVDA", "ABBV", "ADSK")
PAYLOAD_VERSION = "phase5a_v1"


def _finite_or_none(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return float(v) if isinstance(v, float) else int(v)
    return v


def _clean(obj: Any) -> Any:
    """Recursively replace NaN/Inf with None for JSON safety."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return _finite_or_none(obj) if isinstance(obj, float) else obj


def _assoc(c: dict[str, Any], form: str, metric: str) -> dict[str, Any]:
    return (((c.get("stats_phase2") or {}).get("by_form") or {}).get(form) or {}).get(metric) or {}


def _metric_block(assoc: dict[str, Any], *, secondary: bool = False) -> dict[str, Any]:
    raw = assoc.get("raw_pearson") or {}
    spear = assoc.get("spearman") or {}
    agree = assoc.get("agreement") or {}
    n = int(assoc.get("n") or 0)
    q = assoc.get("fdr_q_value")
    rate = agree.get("rate")
    block = {
        "form_type": assoc.get("form_type"),
        "metric": assoc.get("metric"),
        "association_kind": "contemporaneous_same_filing",
        "secondary": secondary,
        "n": n,
        "spearman_rho": spear.get("rho"),
        "spearman_p": spear.get("p_value"),
        "pearson_r": raw.get("r"),
        "pearson_p": raw.get("p_value"),
        "pearson_ci_low": raw.get("ci_low"),
        "pearson_ci_high": raw.get("ci_high"),
        "fdr_q": q,
        "agreement_num": agree.get("agree"),
        "agreement_den": agree.get("eligible"),
        "agreement_pct": (float(rate) * 100.0) if rate is not None else None,
        "agreement_label": agree.get("label"),
        "reliability": assoc.get("reliability"),
    }
    return _clean(block)


def _coverage(c: dict[str, Any]) -> dict[str, Any]:
    points = c.get("points") or []
    n_10q = sum(1 for p in points if form_bucket(p.get("form")) == FORM_10Q)
    n_10k = sum(1 for p in points if form_bucket(p.get("form")) == FORM_10K)
    ni_q = _assoc(c, FORM_10Q, "net_income")
    rev_q = _assoc(c, FORM_10Q, "revenue")
    return {
        "n_filings_scored": int(c.get("n_filings") or 0),
        "n_10q": n_10q,
        "n_10k": n_10k,
        "n_10q_ni_pairs": int(ni_q.get("n") or 0),
        "n_10q_revenue_pairs": int(rev_q.get("n") or 0),
    }


def _chart_points(c: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in c.get("points") or []:
        acc = p.get("accession")
        if not acc or acc in seen:
            continue
        seen.add(acc)
        out.append(
            {
                "accession": acc,
                "form": p.get("form"),
                "filed": p.get("filed"),
                "report_date": p.get("report_date"),
                "sentiment": p.get("sentiment"),
                "income_pct": p.get("income_pct"),
                "revenue_pct": p.get("revenue_pct"),
            }
        )
    return _clean(out)


def _revenue_payload(c: dict[str, Any]) -> dict[str, Any]:
    sector = c.get("sector") or ""
    if sector in NON_COMPARABLE_REVENUE_SECTORS:
        return {
            "available": False,
            "reason": "sector_not_comparable_revenue",
            "sector": sector,
            "note": "ASC-606-style revenue is non-comparable for Financials / Real Estate.",
            "stats": None,
        }
    assoc = _assoc(c, FORM_10Q, "revenue")
    n = int(assoc.get("n") or 0)
    if n <= 0:
        return {
            "available": False,
            "reason": "no_valid_revenue_pairs",
            "sector": sector,
            "stats": None,
        }
    return {
        "available": True,
        "reason": None,
        "sector": sector,
        "stats": _metric_block(assoc, secondary=True),
    }


def _ranking_fields(ni: dict[str, Any]) -> dict[str, Any]:
    n = int(ni.get("n") or 0)
    q = ni.get("fdr_q")
    eligible_default = n >= PUBLIC_RANK_N and ni.get("pearson_r") is not None
    eligible_limited = (LIMITED_RANK_N <= n < PUBLIC_RANK_N) and ni.get("pearson_r") is not None
    return {
        "primary_metric": "10q_net_income",
        "public_rank_min_n": PUBLIC_RANK_N,
        "limited_sample_min_n": LIMITED_RANK_N,
        "ranking_eligible_default": eligible_default,  # n >= 8
        "ranking_eligible_limited": eligible_limited,  # n = 6–7
        "ranking_insufficient": n < LIMITED_RANK_N,
        "sort_spearman_rho": ni.get("spearman_rho") if eligible_default else None,
        "sort_pearson_r": ni.get("pearson_r") if eligible_default else None,
        "sort_agreement_pct": ni.get("agreement_pct") if eligible_default else None,
        "sort_n": n if eligible_default else None,
        "sort_fdr_q": q if eligible_default else None,
        "fdr_significant": bool(q is not None and float(q) < 0.05),
        "fdr_significant_note": "q < 0.05 among ranking-eligible companies; not proof or certainty.",
    }


def build_company_payload_row(c: dict[str, Any], *, featured: bool = False) -> dict[str, Any]:
    ni = _metric_block(_assoc(c, FORM_10Q, "net_income"), secondary=False)
    ni_k = _metric_block(_assoc(c, FORM_10K, "net_income"), secondary=True)
    rev = _revenue_payload(c)
    ranking = _ranking_fields(ni)
    coverage = _coverage(c)
    points = _chart_points(c)

    # Legacy columns retained for backwards-compatible UI until frontend migrates.
    # Values are EXPLICITLY the Phase 4 primary 10-Q NI fields (not pooled),
    # so a transitional sync does not keep publishing combined 10-K+10-Q ranks.
    legacy = {
        "r_income": ni.get("pearson_r"),
        "p_income": ni.get("pearson_p"),
        "n_income": ni.get("n") or 0,
        "r_revenue": (rev.get("stats") or {}).get("pearson_r") if rev.get("available") else None,
        "p_revenue": (rev.get("stats") or {}).get("pearson_p") if rev.get("available") else None,
        "n_revenue": int((rev.get("stats") or {}).get("n") or 0) if rev.get("available") else 0,
        "agreement_income": (
            (ni.get("agreement_pct") / 100.0) if ni.get("agreement_pct") is not None else None
        ),
        "agreement_revenue": (
            ((rev.get("stats") or {}).get("agreement_pct") / 100.0)
            if rev.get("available") and (rev.get("stats") or {}).get("agreement_pct") is not None
            else None
        ),
    }

    row = {
        "ticker": c["ticker"],
        "display": c.get("display") or c["ticker"],
        "name": c.get("name") or c["ticker"],
        "sector": c.get("sector") or "Unknown",
        "cik": c.get("cik"),
        "payload_version": PAYLOAD_VERSION,
        "n_filings": coverage["n_filings_scored"],
        "mean_sentiment": c.get("mean_sentiment"),
        "coverage": coverage,
        "primary_10q_ni": ni,
        "secondary_10q_revenue": rev,
        "secondary_10k_ni": ni_k,
        "ranking": ranking,
        # Flat sortable mirrors for SQL / indexes (primary = 10-Q NI)
        "n_10q_ni": ni.get("n") or 0,
        "spearman_rho_10q_ni": ni.get("spearman_rho"),
        "spearman_p_10q_ni": ni.get("spearman_p"),
        "pearson_r_10q_ni": ni.get("pearson_r"),
        "pearson_p_10q_ni": ni.get("pearson_p"),
        "pearson_ci_low_10q_ni": ni.get("pearson_ci_low"),
        "pearson_ci_high_10q_ni": ni.get("pearson_ci_high"),
        "fdr_q_10q_ni": ni.get("fdr_q"),
        "agreement_num_10q_ni": ni.get("agreement_num"),
        "agreement_den_10q_ni": ni.get("agreement_den"),
        "agreement_pct_10q_ni": ni.get("agreement_pct"),
        "reliability_10q_ni": ni.get("reliability"),
        "ranking_eligible_default": ranking["ranking_eligible_default"],
        "ranking_eligible_limited": ranking["ranking_eligible_limited"],
        "fdr_significant": ranking["fdr_significant"],
        "points": points,
        "featured": featured,
        "exclude_from_sector": bool(c.get("exclude_from_sector")),
        # Legacy (deprecated) — populated from 10-Q NI primary, not pooled combined
        **legacy,
        "legacy_note": (
            "r_income/n_income/agreement_income mirror primary_10q_ni Pearson/agreement "
            "for transitional UI. Prefer spearman_rho_10q_ni + fdr_q_10q_ni. "
            "Do not treat legacy fields as pooled 10-K+10-Q."
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _clean(row)


def build_sector_payload_row(s: dict[str, Any]) -> dict[str, Any]:
    block = (((s.get("stats_phase2") or {}).get("by_form") or {}).get(FORM_10Q) or {}).get(
        "net_income"
    ) or {}
    fw = block.get("filing_weighted") or {}
    fw_raw = fw.get("raw_pearson") or {}
    fw_sp = fw.get("spearman") or {}
    fw_w = fw.get("winsorized_pearson") or {}
    fw_ag = block.get("filing_weighted_agreement") or {}
    cb = block.get("company_balanced") or {}
    cb_ag = block.get("company_balanced_agreement") or {}

    rev_block = (((s.get("stats_phase2") or {}).get("by_form") or {}).get(FORM_10Q) or {}).get(
        "revenue"
    ) or {}
    sector_name = s["sector"]
    rev_available = sector_name not in NON_COMPARABLE_REVENUE_SECTORS

    # Compact display points (already capped in rollup)
    points = []
    for p in s.get("points") or []:
        points.append(
            {
                "ticker": p.get("ticker"),
                "accession": p.get("accession"),
                "form": p.get("form"),
                "filed": p.get("filed"),
                "sentiment": p.get("sentiment"),
                "income_pct": p.get("income_pct"),
                "revenue_pct": p.get("revenue_pct") if rev_available else None,
            }
        )

    ten_q_ni = {
        "filing_weighted_pearson_r": fw_raw.get("r"),
        "filing_weighted_pearson_p": fw_raw.get("p_value"),
        "filing_weighted_spearman_rho": fw_sp.get("rho"),
        "filing_weighted_spearman_p": fw_sp.get("p_value"),
        "winsorized_pearson_r": fw_w.get("r") if int(fw.get("n") or 0) >= 20 else None,
        "filing_n": fw.get("n"),
        "filing_weighted_agreement_label": fw_ag.get("label"),
        "filing_weighted_agreement_rate": fw_ag.get("rate"),
        "company_balanced_pearson_r": cb.get("r"),
        "company_balanced_n_companies": cb.get("n_companies"),
        "company_balanced_agreement_rate": cb_ag.get("rate"),
        "note": (
            "Do not reduce to one unexplained correlation. "
            "Filing-weighted pools every valid filing; company-balanced equal-weights eligible companies."
        ),
    }

    row = {
        "sector": sector_name,
        "payload_version": PAYLOAD_VERSION,
        "n_companies": int(s.get("n_companies") or 0),
        "n_filings": int(s.get("n_filings") or 0),
        "mean_sentiment": s.get("mean_sentiment"),
        "primary_10q_ni": _clean(ten_q_ni),
        "revenue_comparable": rev_available,
        "revenue_unavailable_reason": (
            None if rev_available else "sector_not_comparable_revenue"
        ),
        "secondary_10q_revenue": _clean(
            {
                "available": rev_available,
                "filing_weighted_pearson_r": ((rev_block.get("filing_weighted") or {}).get("raw_pearson") or {}).get(
                    "r"
                )
                if rev_available
                else None,
                "company_balanced_pearson_r": (rev_block.get("company_balanced") or {}).get("r")
                if rev_available
                else None,
            }
        ),
        # Flat mirrors
        "fw_pearson_r_10q_ni": ten_q_ni["filing_weighted_pearson_r"],
        "fw_spearman_rho_10q_ni": ten_q_ni["filing_weighted_spearman_rho"],
        "fw_winsor_r_10q_ni": ten_q_ni["winsorized_pearson_r"],
        "fw_n_10q_ni": ten_q_ni["filing_n"],
        "cb_pearson_r_10q_ni": ten_q_ni["company_balanced_pearson_r"],
        "cb_n_companies_10q_ni": ten_q_ni["company_balanced_n_companies"],
        "points": _clean(points),
        # Legacy transitional: filing-weighted Pearson (not company-balanced)
        "r_income": ten_q_ni["filing_weighted_pearson_r"],
        "p_income": ten_q_ni["filing_weighted_pearson_p"],
        "n_income": int(ten_q_ni["filing_n"] or 0),
        "r_revenue": None
        if not rev_available
        else ((rev_block.get("filing_weighted") or {}).get("raw_pearson") or {}).get("r"),
        "p_revenue": None
        if not rev_available
        else ((rev_block.get("filing_weighted") or {}).get("raw_pearson") or {}).get("p_value"),
        "n_revenue": 0
        if not rev_available
        else int((rev_block.get("filing_weighted") or {}).get("n") or 0),
        "agreement_income": ten_q_ni["filing_weighted_agreement_rate"],
        "agreement_revenue": None,
        "legacy_note": (
            "r_income mirrors filing-weighted 10-Q NI Pearson only. "
            "Prefer primary_10q_ni dual-weight fields."
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _clean(row)


def pick_phase5_featured(companies: list[dict[str, Any]]) -> dict[str, str]:
    """Featured examples from Phase 4 research recommendations (not legacy pooled r)."""
    by = {c["ticker"]: c for c in companies}
    roles: dict[str, str] = {}
    preferred = [
        ("AAPL", "fdr_positive"),
        ("ADI", "fdr_positive"),
        ("AMZN", "negative_not_fdr"),
        ("MSFT", "positive_not_fdr"),
        ("NVDA", "high_agreement"),
        ("ABBV", "near_zero"),
        ("ADSK", "near_zero"),
    ]
    for t, role in preferred:
        if t in by:
            roles[t] = role
    # Add strongest FDR survivor if not already present
    survivors = []
    for c in companies:
        ni = _assoc(c, FORM_10Q, "net_income")
        q = ni.get("fdr_q_value")
        n = int(ni.get("n") or 0)
        r = (ni.get("raw_pearson") or {}).get("r")
        if q is not None and float(q) < 0.05 and n >= PUBLIC_RANK_N and r is not None:
            survivors.append((c["ticker"], float(r)))
    survivors.sort(key=lambda x: x[1], reverse=True)
    for t, _ in survivors[:2]:
        if t not in roles:
            roles[t] = "fdr_positive"
    return roles


def build_example_filings(
    companies: list[dict[str, Any]],
    roles: dict[str, str],
    *,
    include_sentences: bool = True,
    max_sentences: int = 40,
) -> list[dict[str, Any]]:
    """Slim case-study rows. Sentences capped; no MD&A HTML / full corpus dumps."""
    examples: list[dict[str, Any]] = []
    for ticker, role in roles.items():
        accession = latest_analyzed_accession(ticker, prefer_10k=False)
        if not accession:
            continue
        try:
            ex = example_filing_payload(accession, role, risk=None)
        except KeyError:
            continue
        if include_sentences:
            sents = list(ex.get("sentences") or [])[:max_sentences]
            ex["sentences"] = sents
            ex["sentence_count"] = len(sents)
        else:
            ex["sentences"] = []
            ex["sentence_count"] = 0
        # Drop risk blobs in dry-run (optional bias demo stays local until UI asks)
        for k in (
            "risk_sentiment_score",
            "risk_positive_share",
            "risk_negative_share",
            "risk_sentence_count",
            "risk_sentences",
        ):
            ex.pop(k, None)
        ex["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        ex["updated_at"] = datetime.now(timezone.utc).isoformat()
        examples.append(_clean(ex))
    return examples


def build_full_payload() -> dict[str, Any]:
    """Build companies + sectors + examples from local Phase 3 DB."""
    db.init_db()
    companies_raw = build_company_stats()
    plan = registrant_plan()
    alias_set = {a for item in plan for a in item.get("alias_tickers") or []}
    for row in companies_raw:
        if row["ticker"] in alias_set:
            row["exclude_from_sector"] = True
            row["_alias_share_class"] = True

    sector_input = [c for c in companies_raw if not c.get("exclude_from_sector")]
    sectors_raw = build_sector_stats(sector_input)

    roles = pick_phase5_featured(companies_raw)
    company_rows = [
        build_company_payload_row(c, featured=(c["ticker"] in roles)) for c in companies_raw
    ]
    sector_rows = [build_sector_payload_row(s) for s in sectors_raw]
    examples = build_example_filings(companies_raw, roles)

    return {
        "companies": company_rows,
        "sectors": sector_rows,
        "example_filings": examples,
        "meta": {
            "payload_version": PAYLOAD_VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "public_rank_min_n": PUBLIC_RANK_N,
            "alias_excluded_from_sector": sorted(alias_set),
            "featured_roles": roles,
            "upload": False,
        },
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return validation results; raises nothing — collect all issues."""
    companies = payload["companies"]
    sectors = payload["sectors"]
    examples = payload["example_filings"]
    errors: list[str] = []
    warnings: list[str] = []

    tickers = [c["ticker"] for c in companies]
    if len(tickers) != len(set(tickers)):
        errors.append("duplicate ticker rows in companies")

    sectors_names = [s["sector"] for s in sectors]
    if len(sectors_names) != len(set(sectors_names)):
        errors.append("duplicate sector rows")

    alias_in_sector = [c["ticker"] for c in companies if c.get("exclude_from_sector")]
    sector_company_sum = sum(int(s["n_companies"] or 0) for s in sectors)
    non_alias = len(companies) - len(alias_in_sector)
    if sector_company_sum != non_alias:
        warnings.append(
            f"sector n_companies sum={sector_company_sum} vs non-alias companies={non_alias}"
        )

    for c in companies:
        t = c["ticker"]
        accs = [p.get("accession") for p in c.get("points") or []]
        if len(accs) != len(set(accs)):
            errors.append(f"{t}: duplicate accessions in points")

        ni = c.get("primary_10q_ni") or {}
        if c.get("pearson_r_10q_ni") != ni.get("pearson_r"):
            errors.append(f"{t}: flat pearson_r_10q_ni != primary_10q_ni.pearson_r")
        if c.get("spearman_rho_10q_ni") != ni.get("spearman_rho"):
            errors.append(f"{t}: flat spearman swapped/mismatch")
        if c.get("fdr_q_10q_ni") != ni.get("fdr_q"):
            errors.append(f"{t}: fdr_q flat mismatch")
        if c.get("pearson_p_10q_ni") == c.get("fdr_q_10q_ni") and c.get("fdr_q_10q_ni") is not None:
            if c.get("pearson_p_10q_ni") != c.get("fdr_q_10q_ni"):
                pass
            # same numeric value can happen rarely; only warn if labels swapped in ranking
        ci_lo, ci_hi = ni.get("pearson_ci_low"), ni.get("pearson_ci_high")
        r = ni.get("pearson_r")
        if r is not None and ci_lo is not None and ci_hi is not None:
            if not (ci_lo <= r <= ci_hi):
                # floating edge: allow tiny epsilon
                if not (ci_lo - 1e-9 <= r <= ci_hi + 1e-9):
                    errors.append(f"{t}: Pearson r outside CI")

        an, ad = ni.get("agreement_num"), ni.get("agreement_den")
        if an is not None and ad is not None and int(an) > int(ad):
            errors.append(f"{t}: agreement numerator > denominator")

        if c.get("ranking_eligible_default") and int(ni.get("n") or 0) < PUBLIC_RANK_N:
            errors.append(f"{t}: ranking_eligible_default but n<8")
        if c.get("ranking", {}).get("sort_spearman_rho") is not None and not c.get(
            "ranking_eligible_default"
        ):
            errors.append(f"{t}: sort fields present while not default-eligible")

        sector = c.get("sector")
        rev = c.get("secondary_10q_revenue") or {}
        if sector in NON_COMPARABLE_REVENUE_SECTORS:
            if rev.get("available"):
                errors.append(f"{t}: Financials/RE revenue marked available")
            if c.get("r_revenue") is not None or int(c.get("n_revenue") or 0) > 0:
                errors.append(f"{t}: Financials/RE legacy revenue leaked")

        for key in (
            "spearman_rho_10q_ni",
            "pearson_r_10q_ni",
            "fdr_q_10q_ni",
            "agreement_pct_10q_ni",
        ):
            v = c.get(key)
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                errors.append(f"{t}: non-finite {key}")

        # Primary must be 10-Q labeled
        if ni.get("form_type") not in (None, FORM_10Q) and int(ni.get("n") or 0) > 0:
            # form_type set in analyze_pairs
            if ni.get("form_type") != FORM_10Q:
                errors.append(f"{t}: primary form_type is not 10-Q")

    default_board = [c for c in companies if c.get("ranking_eligible_default")]
    if any(int(c.get("n_10q_ni") or 0) < PUBLIC_RANK_N for c in default_board):
        errors.append("n<8 company entered default rankings")

    for s in sectors:
        if s["sector"] in NON_COMPARABLE_REVENUE_SECTORS:
            if s.get("revenue_comparable"):
                errors.append(f"sector {s['sector']}: revenue_comparable true")
            if s.get("r_revenue") is not None or int(s.get("n_revenue") or 0) > 0:
                errors.append(f"sector {s['sector']}: revenue leak")

    # JSON round-trip finiteness
    try:
        blob = json.dumps(payload, allow_nan=False, default=str)
    except ValueError as e:
        errors.append(f"JSON NaN/Inf serialization failed: {e}")
        blob = ""

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "n_companies": len(companies),
        "n_sectors": len(sectors),
        "n_examples": len(examples),
        "n_default_rank": len(default_board),
        "n_fdr_significant": sum(1 for c in companies if c.get("fdr_significant")),
        "n_limited": sum(1 for c in companies if c.get("ranking_eligible_limited")),
        "serialized_ok": bool(blob),
    }


def footprint(payload: dict[str, Any]) -> dict[str, Any]:
    companies = payload["companies"]
    sectors = payload["sectors"]
    examples = payload["example_filings"]
    c_bytes = len(json.dumps(companies, default=str).encode("utf-8"))
    s_bytes = len(json.dumps(sectors, default=str).encode("utf-8"))
    e_bytes = len(json.dumps(examples, default=str).encode("utf-8"))
    total = c_bytes + s_bytes + e_bytes
    largest_c = max(companies, key=lambda r: len(json.dumps(r, default=str).encode("utf-8")))
    largest_c_n = len(json.dumps(largest_c, default=str).encode("utf-8"))
    # Largest field among companies
    field_sizes: dict[str, int] = {}
    for c in companies:
        for k, v in c.items():
            sz = len(json.dumps(v, default=str).encode("utf-8"))
            field_sizes[k] = max(field_sizes.get(k, 0), sz)
    largest_field = max(field_sizes.items(), key=lambda kv: kv[1])
    chart_points = sum(len(c.get("points") or []) for c in companies)
    null_rev = sum(1 for c in companies if not (c.get("secondary_10q_revenue") or {}).get("available"))
    est_pg = int(total * 2.2 + 2_000_000)
    return {
        "company_rows": len(companies),
        "sector_rows": len(sectors),
        "example_rows": len(examples),
        "chart_points": chart_points,
        "companies_json_mb": round(c_bytes / 1024 / 1024, 3),
        "sectors_json_mb": round(s_bytes / 1024 / 1024, 3),
        "examples_json_mb": round(e_bytes / 1024 / 1024, 3),
        "total_json_mb": round(total / 1024 / 1024, 3),
        "estimated_postgres_mb": round(est_pg / 1024 / 1024, 2),
        "largest_company_ticker": largest_c.get("ticker"),
        "largest_company_kb": round(largest_c_n / 1024, 2),
        "largest_json_field": largest_field[0],
        "largest_json_field_kb": round(largest_field[1] / 1024, 2),
        "null_revenue_metrics_companies": null_rev,
        "n_eligible_n8": sum(1 for c in companies if c.get("ranking_eligible_default")),
        "n_fdr_q_lt_05": sum(1 for c in companies if c.get("fdr_significant")),
        "safely_below_500mb": est_pg < 500 * 1024 * 1024,
    }


def verify_case_studies(payload: dict[str, Any], phase4_cases: Optional[list[dict[str, Any]]] = None) -> list[dict[str, Any]]:
    by = {c["ticker"]: c for c in payload["companies"]}
    out = []
    for t in CASE_STUDY_TICKERS:
        c = by.get(t)
        if not c:
            out.append({"ticker": t, "ok": False, "error": "missing"})
            continue
        ni = c["primary_10q_ni"]
        row = {
            "ticker": t,
            "n": ni.get("n"),
            "spearman_rho": ni.get("spearman_rho"),
            "pearson_r": ni.get("pearson_r"),
            "pearson_p": ni.get("pearson_p"),
            "fdr_q": ni.get("fdr_q"),
            "fdr_significant": c.get("fdr_significant"),
            "agreement_label": ni.get("agreement_label"),
            "ranking_eligible_default": c.get("ranking_eligible_default"),
        }
        if phase4_cases:
            p4 = next((x for x in phase4_cases if x.get("ticker") == t), None)
            if p4 and p4.get("10q_ni"):
                p4ni = p4["10q_ni"]
                row["phase4_match"] = (
                    abs(float(ni.get("pearson_r") or 0) - float(p4ni.get("pearson_r") or 0)) < 1e-9
                    and int(ni.get("n") or -1) == int(p4ni.get("n") or -2)
                )
        out.append(row)
    return out
