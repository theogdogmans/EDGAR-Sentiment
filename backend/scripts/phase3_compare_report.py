#!/usr/bin/env python3
"""Compare legacy cloud snapshot vs Phase 3 rebuilt Phase 2 stats."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import os

os.environ.setdefault("PHASE3_DB_NAME", "edgar_phase3.db")

from app import db  # noqa: E402
from app.compare.rollup import (  # noqa: E402
    build_company_stats,
    build_sector_stats,
    ranking_eligibility_counts,
)
from app.compare.stats_core import FORM_10Q, distribution_summary, form_bucket  # noqa: E402


FOCUS = ["AAPL", "ADI", "ABBV", "ADSK", "AFL", "AES"]


def _fmt(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _assoc(c: dict[str, Any], form: str = FORM_10Q, metric: str = "net_income") -> dict[str, Any]:
    return (((c.get("stats_phase2") or {}).get("by_form") or {}).get(form) or {}).get(metric) or {}


def main() -> int:
    legacy_path = ROOT / "backend" / "data" / "legacy_backup" / "company_stats_latest.json"
    if not legacy_path.exists():
        legacy_path = ROOT / "backend" / "data" / "audit_company_stats.json"
    legacy_raw = json.loads(legacy_path.read_text())
    legacy_companies = legacy_raw.get("companies") or legacy_raw
    legacy_by = {c["ticker"]: c for c in legacy_companies}

    db.init_db()
    companies = build_company_stats()
    sectors = build_sector_stats(companies)
    by = {c["ticker"]: c for c in companies}

    qcounts = db.quality_log_counts()
    logs = [dict(r) for r in db.list_quality_logs()]
    fail_reasons: dict[str, int] = {}
    for lg in logs:
        fr = lg.get("failure_reason") or ("ok" if lg.get("sentiment_score") is not None else "unknown")
        # normalize
        key = fr.split(";")[0][:120]
        fail_reasons[key] = fail_reasons.get(key, 0) + 1

    ni_yoy_q = [float(lg["ni_yoy"]) for lg in logs if lg.get("ni_status") == "ok" and lg.get("form", "").startswith("10-Q") and lg.get("ni_yoy") is not None]
    ni_yoy_k = [float(lg["ni_yoy"]) for lg in logs if lg.get("ni_status") == "ok" and lg.get("form", "").startswith("10-K") and lg.get("ni_yoy") is not None]

    # Rankings 10-Q NI
    def rank_table(min_n: int) -> dict[str, list[dict[str, Any]]]:
        rows = []
        for c in companies:
            a = _assoc(c, FORM_10Q, "net_income")
            n = int(a.get("n") or 0)
            if n < min_n:
                continue
            raw = a.get("raw_pearson") or {}
            spear = a.get("spearman") or {}
            agree = a.get("agreement") or {}
            rows.append(
                {
                    "ticker": c["ticker"],
                    "name": c.get("name"),
                    "sector": c.get("sector"),
                    "n": n,
                    "r": raw.get("r"),
                    "p": raw.get("p_value"),
                    "q": a.get("fdr_q_value"),
                    "ci_low": raw.get("ci_low"),
                    "ci_high": raw.get("ci_high"),
                    "rho": spear.get("rho"),
                    "spearman_p": spear.get("p_value"),
                    "agree": agree.get("label"),
                    "agree_rate": agree.get("rate"),
                    "reliability": a.get("reliability"),
                }
            )

        by_r = sorted([r for r in rows if r["r"] is not None], key=lambda x: float(x["r"]), reverse=True)
        by_rho = sorted([r for r in rows if r["rho"] is not None], key=lambda x: float(x["rho"]), reverse=True)
        both = sorted(
            [r for r in rows if r["r"] is not None and r["rho"] is not None and float(r["r"]) > 0 and float(r["rho"]) > 0],
            key=lambda x: min(float(x["r"]), float(x["rho"])),
            reverse=True,
        )
        neg = sorted([r for r in rows if r["r"] is not None], key=lambda x: float(x["r"]))
        disagree = sorted(
            [r for r in rows if r["r"] is not None and r["rho"] is not None],
            key=lambda x: abs(float(x["r"]) - float(x["rho"])),
            reverse=True,
        )
        agree_hi = sorted(
            [r for r in rows if r.get("agree_rate") is not None],
            key=lambda x: float(x["agree_rate"]),
            reverse=True,
        )
        p05 = [r for r in rows if r.get("p") is not None and float(r["p"]) < 0.05]
        q05 = [r for r in rows if r.get("q") is not None and float(r["q"]) < 0.05]
        return {
            "strongest_pearson": by_r[:15],
            "strongest_spearman": by_rho[:15],
            "strongest_both": both[:15],
            "strongest_negative": neg[:15],
            "largest_pearson_spearman_gap": disagree[:15],
            "highest_agreement": agree_hi[:15],
            "p_lt_05": sorted(p05, key=lambda x: float(x["p"]))[:30],
            "fdr_q_lt_05": sorted(q05, key=lambda x: float(x["q"]))[:30],
        }

    focus = []
    for t in FOCUS:
        leg = legacy_by.get(t)
        neu = by.get(t)
        focus.append(
            {
                "ticker": t,
                "legacy": {
                    "r_income": None if not leg else leg.get("r_income"),
                    "n_income": None if not leg else leg.get("n_income"),
                    "n_filings": None if not leg else leg.get("n_filings"),
                },
                "phase3_10q_ni": _assoc(neu, FORM_10Q, "net_income") if neu else None,
                "phase3_combined_ni": _assoc(neu, "combined", "net_income") if neu else None,
            }
        )

    legacy_summary = legacy_raw.get("summary") or {
        "n_companies_with_points": len(legacy_companies),
        "n_filings_in_points": sum(len(c.get("points") or []) for c in legacy_companies),
    }

    out = {
        "legacy": legacy_summary,
        "phase3_quality": qcounts,
        "phase3_coverage": db.coverage(),
        "eligibility_10q_ni": ranking_eligibility_counts(companies, form=FORM_10Q, metric="net_income"),
        "eligibility_combined_ni": ranking_eligibility_counts(companies, form="combined", metric="net_income"),
        "failure_reason_counts": dict(sorted(fail_reasons.items(), key=lambda kv: -kv[1])[:40]),
        "ni_yoy_dist_10q": distribution_summary(ni_yoy_q),
        "ni_yoy_dist_10k": distribution_summary(ni_yoy_k),
        "focus_companies": focus,
        "rankings_n6": rank_table(6),
        "rankings_n8": rank_table(8),
        "sectors": [
            {
                "sector": s["sector"],
                "n_companies": s["n_companies"],
                "n_filings": s["n_filings"],
                "legacy_r_income": s.get("r_income"),
                "phase2_10q": ((s.get("stats_phase2") or {}).get("by_form") or {}).get(FORM_10Q),
            }
            for s in sectors
        ],
    }

    out_path = ROOT / "backend" / "data" / "phase3" / "legacy_vs_phase3.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str))

    # Human-readable stdout
    print("=" * 72)
    print("LEGACY vs PHASE 3")
    print("=" * 72)
    print("Legacy:", json.dumps(legacy_summary, indent=2))
    print("Phase3 quality:", qcounts)
    print("Eligibility 10-Q NI:", out["eligibility_10q_ni"])
    print("\nFocus companies:")
    for row in focus:
        a = row.get("phase3_10q_ni") or {}
        raw = a.get("raw_pearson") or {}
        spear = a.get("spearman") or {}
        print(
            f"  {row['ticker']}: legacy r={_fmt(row['legacy']['r_income'])} n={row['legacy']['n_income']} | "
            f"10-Q r={_fmt(raw.get('r'))} ρ={_fmt(spear.get('rho'))} n={a.get('n')} p={_fmt(raw.get('p_value'))}"
        )
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
