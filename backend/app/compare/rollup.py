from __future__ import annotations

import json
from typing import Any, Optional

from .. import db
from .metrics import _corr, summarize


def _point(filing: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    metrics = analysis.get("metrics") or {}
    sent = analysis.get("sentiment") or {}
    return {
        "accession": filing["accession"],
        "form": filing["form"],
        "filed": filing["filed"],
        "sentiment": sent.get("score"),
        "income_pct": (metrics.get("net_income") or {}).get("pct_change"),
        "revenue_pct": (metrics.get("revenue") or {}).get("pct_change"),
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


def build_company_stats() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sp in db.list_sp500():
        ticker = sp["ticker"]
        filings = company_filings_payload(ticker)
        summary = summarize(filings)
        points = []
        scores: list[float] = []
        for f in filings:
            if not f.get("sentiment"):
                continue
            scores.append(float(f["sentiment"]["score"]))
            points.append(_point(f, f))
        income = summary["correlation"]["net_income"] or {}
        revenue = summary["correlation"]["revenue"] or {}
        rows.append(
            {
                "ticker": ticker,
                "display": sp["display"] or ticker,
                "name": sp["name"],
                "sector": sp["sector"] or "Unknown",
                "cik": sp["cik"],
                "n_filings": int(summary["analyzed_count"]),
                "mean_sentiment": float(sum(scores) / len(scores)) if scores else None,
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
            }
        )
    return rows


def build_sector_stats(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
                    }
                )
                if p.get("income_pct") is not None:
                    income_x.append(float(s))
                    income_y.append(float(p["income_pct"]))
                if p.get("revenue_pct") is not None:
                    revenue_x.append(float(s))
                    revenue_y.append(float(p["revenue_pct"]))

        # Cap pooled scatter size for free-tier JSON
        if len(pooled_points) > 400:
            step = max(1, len(pooled_points) // 400)
            pooled_points = pooled_points[::step][:400]

        income = _corr(income_x, income_y) or {}
        revenue = _corr(revenue_x, revenue_y) or {}
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
                "agreement_income": (sum(agree_income) / len(agree_income)) if agree_income else None,
                "agreement_revenue": (sum(agree_revenue) / len(agree_revenue)) if agree_revenue else None,
                "points": pooled_points,
            }
        )
    return out


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

    # Fill remaining with next-best absolute correlations
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
