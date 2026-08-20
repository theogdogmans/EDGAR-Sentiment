"""Industry / company rollups.

Production sync continues to publish legacy pooled fields (``r_income``, …)
so the live UI is unchanged. Phase 2 results are attached under
``stats_phase2`` and can be stored locally without mutating raw analyses.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .. import db
from .metrics import _corr, summarize, summarize_phase2
from .stats_core import (
    FORM_10K,
    FORM_10Q,
    FORM_COMBINED,
    MIN_N_RANKING,
    MIN_N_RANKING_STRICT,
    agreement_counts,
    analyze_pairs,
    benjamini_hochberg,
    fisher_mean_r,
    form_bucket,
    reliability_class,
)


def _point(filing: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    metrics = analysis.get("metrics") or {}
    sent = analysis.get("sentiment") or {}
    ni = metrics.get("net_income") or {}
    rev = metrics.get("revenue") or {}
    return {
        "accession": filing["accession"],
        "form": filing["form"],
        "filed": filing["filed"],
        "report_date": filing.get("report_date"),
        "sentiment": sent.get("score"),
        "income_pct": ni.get("pct_change"),
        "revenue_pct": rev.get("pct_change"),
        # Optional levels for outlier diagnostics (never overwrite YoY)
        "income_current": ni.get("current"),
        "income_prior": ni.get("prior"),
        "revenue_current": rev.get("current"),
        "revenue_prior": rev.get("prior"),
    }


def company_filings_payload(ticker: str) -> list[dict[str, Any]]:
    """Build the same shape summarize() expects from local SQLite."""
    payload: list[dict[str, Any]] = []
    for row in db.list_filings(ticker):
        filing = dict(row)
        analysis = db.get_analysis(filing["accession"])
        if not analysis:
            filing["sentiment"] = None
            filing["metrics"] = None
            filing["agreement"] = None
            payload.append(filing)
            continue
        parsed = db.analysis_to_dict(analysis)
        filing["sentiment"] = parsed["sentiment"]
        filing["metrics"] = parsed["metrics"]
        filing["agreement"] = parsed["agreement"]
        payload.append(filing)
    return payload


def _flatten_points_as_filings(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Treat compact scatter points as filings for Phase 2 math."""
    return [dict(p) for p in points]


def build_company_stats() -> list[dict[str, Any]]:
    """Legacy production-shaped rows + additive ``stats_phase2`` JSON."""
    rows: list[dict[str, Any]] = []
    for sp in db.list_sp500():
        ticker = sp["ticker"]
        filings = company_filings_payload(ticker)
        summary = summarize(filings)
        phase2 = summarize_phase2(filings)
        points = []
        scores: list[float] = []
        for f in filings:
            if not f.get("sentiment"):
                continue
            scores.append(float(f["sentiment"]["score"]))
            points.append(_point(f, f))
        income = summary["correlation"]["net_income"] or {}
        revenue = summary["correlation"]["revenue"] or {}
        # Primary Phase 2 n for reliability labels (prefer 10-Q income, else combined)
        p2_income_q = phase2["by_form"][FORM_10Q]["net_income"]
        p2_income_k = phase2["by_form"][FORM_10K]["net_income"]
        p2_income_c = phase2["by_form"][FORM_COMBINED]["net_income"]
        rows.append(
            {
                "ticker": ticker,
                "display": sp["display"] or ticker,
                "name": sp["name"],
                "sector": sp["sector"] or "Unknown",
                "cik": sp["cik"],
                "n_filings": int(summary["analyzed_count"]),
                "mean_sentiment": float(sum(scores) / len(scores)) if scores else None,
                # Legacy production fields (pooled) — unchanged semantics for UI sync
                "r_income": income.get("r"),
                "p_income": income.get("p_value"),
                "n_income": int(income.get("n") or 0),
                "r_revenue": revenue.get("r"),
                "p_revenue": revenue.get("p_value"),
                "n_revenue": int(revenue.get("n") or 0),
                "agreement_income": summary["agreement_rate"]["net_income"],
                "agreement_revenue": summary["agreement_rate"]["revenue"],
                "points": points,
                "featured": False,
                "stats_phase2": phase2,
                "reliability_income_10q": reliability_class(int(p2_income_q.get("n") or 0)),
                "reliability_income_10k": reliability_class(int(p2_income_k.get("n") or 0)),
                "reliability_income_combined": reliability_class(int(p2_income_c.get("n") or 0)),
            }
        )
    _attach_company_fdr(rows)
    return rows


def build_company_stats_from_cloud_rows(cloud_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rebuild Phase 2 from exported ``company_stats`` rows (points JSON).

    Used for audits when local SQLite is empty. Does not mutate raw YoY values.
    """
    rows: list[dict[str, Any]] = []
    for c in cloud_rows:
        points = list(c.get("points") or [])
        filings = _flatten_points_as_filings(points)
        summary = summarize(filings)
        phase2 = summarize_phase2(filings)
        income = summary["correlation"]["net_income"] or {}
        revenue = summary["correlation"]["revenue"] or {}
        scores = [float(p["sentiment"]) for p in points if p.get("sentiment") is not None]
        rows.append(
            {
                "ticker": c["ticker"],
                "display": c.get("display") or c["ticker"],
                "name": c.get("name") or c["ticker"],
                "sector": c.get("sector") or "Unknown",
                "cik": c.get("cik"),
                "n_filings": int(c.get("n_filings") or len(scores)),
                "mean_sentiment": float(sum(scores) / len(scores)) if scores else None,
                "r_income": income.get("r") if income.get("r") is not None else c.get("r_income"),
                "p_income": income.get("p_value"),
                "n_income": int(income.get("n") or 0),
                "r_revenue": revenue.get("r") if revenue.get("r") is not None else c.get("r_revenue"),
                "p_revenue": revenue.get("p_value"),
                "n_revenue": int(revenue.get("n") or 0),
                "agreement_income": summary["agreement_rate"]["net_income"],
                "agreement_revenue": summary["agreement_rate"]["revenue"],
                "points": points,
                "featured": bool(c.get("featured")),
                "stats_phase2": phase2,
                "cloud_r_income": c.get("r_income"),
                "cloud_n_income": c.get("n_income"),
            }
        )
    _attach_company_fdr(rows)
    return rows


def _attach_company_fdr(rows: list[dict[str, Any]]) -> None:
    """Benjamini–Hochberg q-values on exploratory company rankings (diagnostic)."""
    for metric in ("net_income", "revenue"):
        for form in (FORM_10Q, FORM_10K, FORM_COMBINED):
            pvals: list[Optional[float]] = []
            for r in rows:
                block = ((r.get("stats_phase2") or {}).get("by_form") or {}).get(form) or {}
                assoc = block.get(metric) or {}
                raw = assoc.get("raw_pearson") or {}
                n = int(assoc.get("n") or 0)
                # FDR pool: ranking-eligible samples only
                if n >= MIN_N_RANKING and raw.get("p_value") is not None:
                    pvals.append(float(raw["p_value"]))
                else:
                    pvals.append(None)
            qvals = benjamini_hochberg(pvals)
            for r, q in zip(rows, qvals):
                block = ((r.get("stats_phase2") or {}).get("by_form") or {}).get(form) or {}
                assoc = block.get(metric) or {}
                assoc["fdr_q_value"] = q
                raw = assoc.get("raw_pearson") or {}
                raw["fdr_q_value"] = q


def build_sector_stats(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Legacy production sector rows + additive Phase 2 dual weighting."""
    by_sector: dict[str, list[dict[str, Any]]] = {}
    for c in companies:
        sector = c.get("sector") or "Unknown"
        by_sector.setdefault(sector, []).append(c)

    out: list[dict[str, Any]] = []
    for sector, members in sorted(by_sector.items()):
        income_x: list[float] = []
        income_y: list[float] = []
        revenue_x: list[float] = []
        revenue_y: list[float] = []
        agree_income: list[float] = []
        agree_revenue: list[float] = []
        means: list[float] = []
        n_filings = 0
        pooled_points: list[dict[str, Any]] = []

        for c in members:
            n_filings += int(c.get("n_filings") or 0)
            if c.get("mean_sentiment") is not None:
                means.append(float(c["mean_sentiment"]))
            if c.get("agreement_income") is not None:
                agree_income.append(float(c["agreement_income"]))
            if c.get("agreement_revenue") is not None:
                agree_revenue.append(float(c["agreement_revenue"]))
            for p in c.get("points") or []:
                s = p.get("sentiment")
                if s is None:
                    continue
                pooled_points.append(
                    {
                        "ticker": c["ticker"],
                        "form": p.get("form"),
                        "filed": p.get("filed"),
                        "sentiment": s,
                        "income_pct": p.get("income_pct"),
                        "revenue_pct": p.get("revenue_pct"),
                        "income_current": p.get("income_current"),
                        "income_prior": p.get("income_prior"),
                    }
                )
                if p.get("income_pct") is not None:
                    income_x.append(float(s))
                    income_y.append(float(p["income_pct"]))
                if p.get("revenue_pct") is not None:
                    revenue_x.append(float(s))
                    revenue_y.append(float(p["revenue_pct"]))

        display_points = pooled_points
        if len(display_points) > 400:
            step = max(1, len(display_points) // 400)
            display_points = display_points[::step][:400]

        income = _corr(income_x, income_y) or {}
        revenue = _corr(revenue_x, revenue_y) or {}
        phase2 = _sector_phase2(members, pooled_points)
        out.append(
            {
                "sector": sector,
                "n_companies": len(members),
                "n_filings": n_filings,
                "mean_sentiment": float(sum(means) / len(means)) if means else None,
                "r_income": income.get("r"),
                "p_income": income.get("p_value"),
                "n_income": int(income.get("n") or 0),
                "r_revenue": revenue.get("r"),
                "p_revenue": revenue.get("p_value"),
                "n_revenue": int(revenue.get("n") or 0),
                # Legacy: mean of company agreement rates (company-balanced agreement)
                "agreement_income": (sum(agree_income) / len(agree_income)) if agree_income else None,
                "agreement_revenue": (sum(agree_revenue) / len(agree_revenue)) if agree_revenue else None,
                "points": display_points,
                "stats_phase2": phase2,
            }
        )
    return out


def _sector_phase2(members: list[dict[str, Any]], pooled_points: list[dict[str, Any]]) -> dict[str, Any]:
    """Filing-weighted vs company-balanced sector associations."""
    by_form: dict[str, Any] = {}
    for form_label, form_filt in (
        (FORM_10Q, FORM_10Q),
        (FORM_10K, FORM_10K),
        (FORM_COMBINED, None),
    ):
        metrics_block: dict[str, Any] = {}
        for metric, y_key in (("net_income", "income_pct"), ("revenue", "revenue_pct")):
            # A) Filing-weighted
            xs: list[float] = []
            ys: list[float] = []
            for p in pooled_points:
                bucket = form_bucket(p.get("form"))
                if form_filt == FORM_10Q and bucket != FORM_10Q:
                    continue
                if form_filt == FORM_10K and bucket != FORM_10K:
                    continue
                if p.get("sentiment") is None or p.get(y_key) is None:
                    continue
                xs.append(float(p["sentiment"]))
                ys.append(float(p[y_key]))
            filing_weighted = analyze_pairs(xs, ys, form_type=form_label, metric=metric)
            filing_agree = agreement_counts(xs, ys)

            # B) Company-balanced: equal-weight Fisher-z mean of company raw Pearson r
            company_rs: list[float] = []
            company_ns: list[int] = []
            company_agree_rates: list[float] = []
            for c in members:
                block = ((c.get("stats_phase2") or {}).get("by_form") or {}).get(form_label) or {}
                assoc = block.get(metric) or {}
                r = (assoc.get("raw_pearson") or {}).get("r")
                n = int(assoc.get("n") or 0)
                if r is not None and n >= MIN_N_RANKING:
                    company_rs.append(float(r))
                    company_ns.append(n)
                agr = assoc.get("agreement") or {}
                if agr.get("rate") is not None:
                    company_agree_rates.append(float(agr["rate"]))

            balanced_r = fisher_mean_r(company_rs)
            metrics_block[metric] = {
                "form_type": form_label,
                "metric": metric,
                "association_kind": "contemporaneous_same_filing",
                "filing_weighted": filing_weighted,
                "filing_weighted_agreement": filing_agree,
                "company_balanced": {
                    "method": "equal_weight_fisher_z_mean_of_company_pearson_r",
                    "r": balanced_r,
                    "n_companies": len(company_rs),
                    "company_ns": company_ns,
                    "note": (
                        "Each eligible company contributes one Pearson r; "
                        "companies with more filings do not dominate."
                    ),
                },
                "company_balanced_agreement": {
                    "method": "mean_of_company_agreement_rates",
                    "rate": (sum(company_agree_rates) / len(company_agree_rates))
                    if company_agree_rates
                    else None,
                    "n_companies": len(company_agree_rates),
                },
            }
        by_form[form_label] = {
            "form_type": form_label,
            "exploratory": form_label == FORM_COMBINED,
            **metrics_block,
        }

    return {
        "association_kind": "contemporaneous_same_filing",
        "approaches": {
            "filing_weighted": "Every valid filing is one observation (companies with more filings weigh more).",
            "company_balanced": "Equal weight per eligible company via Fisher-z mean of company Pearson r.",
        },
        "by_form": by_form,
    }


def pick_featured_tickers(companies: list[dict[str, Any]], limit: int = 8) -> dict[str, str]:
    """Return ticker -> role for example filings (highest/lowest/typical + bias demos)."""
    scored = [c for c in companies if (c.get("n_income") or 0) >= 3 and c.get("r_income") is not None]
    scored.sort(key=lambda c: float(c["r_income"]), reverse=True)
    roles: dict[str, str] = {}

    def add(ticker: str, role: str) -> None:
        if ticker and ticker not in roles and len(roles) < limit:
            roles[ticker] = role

    if scored:
        add(scored[0]["ticker"], "highest_r")
        add(scored[-1]["ticker"], "lowest_r")
        mid = scored[len(scored) // 2]
        add(mid["ticker"], "typical")

    for ticker in ("AAPL", "MSFT", "JPM", "XOM"):
        add(ticker, "bias_demo")

    by_abs = sorted(scored, key=lambda c: abs(float(c["r_income"])), reverse=True)
    for c in by_abs:
        add(c["ticker"], "featured")
        if len(roles) >= limit:
            break
    return roles


def latest_analyzed_accession(ticker: str, *, prefer_10k: bool = False) -> Optional[str]:
    rows = list(db.list_filings(ticker))
    if prefer_10k:
        for row in rows:
            if str(row["form"]).startswith("10-K") and db.get_analysis(row["accession"]):
                return row["accession"]
    for row in rows:
        if db.get_analysis(row["accession"]):
            return row["accession"]
    return None


def example_filing_payload(accession: str, role: str, risk: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    filing = db.get_filing(accession)
    if filing is None:
        raise KeyError(accession)
    analysis = db.get_analysis(accession)
    if analysis is None:
        raise KeyError(f"No analysis for {accession}")
    parsed = db.analysis_to_dict(analysis)
    sent = parsed["sentiment"]
    payload: dict[str, Any] = {
        "accession": accession,
        "ticker": filing["ticker"],
        "form": filing["form"],
        "filed": filing["filed"],
        "report_date": filing["report_date"],
        "filing_url": filing["filing_url"],
        "sentiment_score": sent["score"],
        "positive_share": sent["positive_share"],
        "negative_share": sent["negative_share"],
        "neutral_share": sent["neutral_share"],
        "sentence_count": sent["sentence_count"],
        "metrics": parsed["metrics"],
        "agreement": parsed["agreement"],
        "sentences": parsed["sentences"],
        "role": role,
    }
    if risk:
        payload.update(
            {
                "risk_sentiment_score": risk.get("score"),
                "risk_positive_share": risk.get("positive_share"),
                "risk_negative_share": risk.get("negative_share"),
                "risk_sentence_count": risk.get("sentence_count"),
                "risk_sentences": risk.get("sentences"),
            }
        )
    return payload


def dump_debug(path: str) -> None:
    companies = build_company_stats()
    sectors = build_sector_stats(companies)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"companies": len(companies), "sectors": sectors[:3]}, fh, indent=2)


def ranking_eligibility_counts(companies: list[dict[str, Any]], *, form: str = FORM_COMBINED, metric: str = "net_income") -> dict[str, int]:
    """How many companies meet each n threshold for a form×metric view."""
    counts = {"n_ge_3": 0, "n_ge_6": 0, "n_ge_8": 0, "n_ge_10": 0}
    for c in companies:
        block = ((c.get("stats_phase2") or {}).get("by_form") or {}).get(form) or {}
        n = int((block.get(metric) or {}).get("n") or 0)
        if n >= 3:
            counts["n_ge_3"] += 1
        if n >= MIN_N_RANKING:
            counts["n_ge_6"] += 1
        if n >= MIN_N_RANKING_STRICT:
            counts["n_ge_8"] += 1
        if n >= 10:
            counts["n_ge_10"] += 1
    return counts
