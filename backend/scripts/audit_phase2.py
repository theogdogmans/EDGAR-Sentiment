#!/usr/bin/env python3
"""Phase 2 BEFORE/AFTER audit against currently processed company_stats points.

Does not mutate raw YoY observations or push new production rankings.

Usage:
  PYTHONPATH=backend python backend/scripts/audit_phase2.py path/to/company_stats.json

If no path is given, reads backend/data/audit_company_stats.json when present.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.compare.metrics import agreement_sensitivity, summarize  # noqa: E402
from app.compare.rollup import (  # noqa: E402
    build_company_stats_from_cloud_rows,
    build_sector_stats,
    ranking_eligibility_counts,
)
from app.compare.stats_core import (  # noqa: E402
    FORM_10K,
    FORM_10Q,
    FORM_COMBINED,
    MIN_N_WINSOR,
    distribution_summary,
    flag_ni_outlier,
    form_bucket,
)


def _load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "companies" in data:
        return data["companies"]
    if isinstance(data, list):
        return data
    raise ValueError("Expected list or {companies: [...]}")


def _assoc_line(label: str, assoc: dict[str, Any]) -> str:
    raw = assoc.get("raw_pearson") or {}
    spear = assoc.get("spearman") or {}
    wins = assoc.get("winsorized_pearson") or {}
    agree = assoc.get("agreement") or {}
    r = raw.get("r")
    rho = spear.get("rho")
    wr = wins.get("r")
    p = raw.get("p_value")
    q = assoc.get("fdr_q_value")
    ci = (raw.get("ci_low"), raw.get("ci_high"))
    return (
        f"  {label}: n={assoc.get('n')}  "
        f"Pearson r={_fmt(r)}  Spearman ρ={_fmt(rho)}  "
        f"winsor r={_fmt(wr)}  p={_fmt(p)}  q={_fmt(q)}  "
        f"CI=[{_fmt(ci[0])}, {_fmt(ci[1])}]  "
        f"agree={agree.get('label')}  reliability={assoc.get('reliability')}"
    )


def _fmt(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _pick_companies(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ticker = {c["ticker"]: c for c in companies}
    chosen: list[dict[str, Any]] = []

    def add(t: str) -> None:
        if t in by_ticker and by_ticker[t] not in chosen:
            chosen.append(by_ticker[t])

    add("AAPL")
    for t in ("AES", "ADM", "AFL"):  # NI-outlier heavy names in current corpus
        add(t)
    scored = [c for c in companies if c.get("r_income") is not None and (c.get("n_income") or 0) >= 3]
    scored_pos = sorted(scored, key=lambda c: float(c["r_income"]), reverse=True)
    scored_neg = sorted(scored, key=lambda c: float(c["r_income"]))
    for c in scored_pos[:3]:
        add(c["ticker"])
    for c in scored_neg[:3]:
        add(c["ticker"])

    # Company strongly affected by NI outlier
    worst = None
    worst_abs = -1.0
    for c in companies:
        for p in c.get("points") or []:
            y = p.get("income_pct")
            if y is None:
                continue
            if abs(float(y)) > worst_abs:
                worst_abs = abs(float(y))
                worst = c
    if worst:
        add(worst["ticker"])
    return chosen


def outlier_report(companies: list[dict[str, Any]]) -> dict[str, Any]:
    by_form = {FORM_10Q: [], FORM_10K: []}
    extremes: list[dict[str, Any]] = []
    for c in companies:
        for p in c.get("points") or []:
            bucket = form_bucket(p.get("form"))
            if bucket not in by_form:
                continue
            if p.get("income_pct") is not None:
                by_form[bucket].append(float(p["income_pct"]))
            if p.get("revenue_pct") is not None:
                # collect separately below
                pass
            extremes.append(
                {
                    "ticker": c["ticker"],
                    "company": c.get("name"),
                    "form": p.get("form"),
                    "report_date": p.get("report_date") or p.get("filed"),
                    "current_ni": p.get("income_current"),
                    "prior_ni": p.get("income_prior"),
                    "raw_yoy": p.get("income_pct"),
                    "sentiment": p.get("sentiment"),
                }
            )

    rev_by_form = {FORM_10Q: [], FORM_10K: []}
    for c in companies:
        for p in c.get("points") or []:
            bucket = form_bucket(p.get("form"))
            if bucket in rev_by_form and p.get("revenue_pct") is not None:
                rev_by_form[bucket].append(float(p["revenue_pct"]))

    extremes = [e for e in extremes if e.get("raw_yoy") is not None]
    extremes.sort(key=lambda e: abs(float(e["raw_yoy"])), reverse=True)
    top20 = extremes[:20]
    for e in top20:
        e["flags"] = flag_ni_outlier(
            current=e.get("current_ni"),
            prior=e.get("prior_ni"),
            yoy=float(e["raw_yoy"]) if e.get("raw_yoy") is not None else None,
        )
        if e.get("current_ni") is None and e.get("prior_ni") is None:
            e["flags"].append("prior_levels_unavailable_in_cloud_points")
        # de-dupe
        e["flags"] = list(dict.fromkeys(e["flags"]))

    return {
        "net_income_yoy": {k: distribution_summary(v) for k, v in by_form.items()},
        "revenue_yoy": {k: distribution_summary(v) for k, v in rev_by_form.items()},
        "top20_extreme_ni_yoy": top20,
    }


def classify_story(old_r: Optional[float], new_blocks: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    q = new_blocks.get(FORM_10Q, {}).get("net_income") or {}
    k = new_blocks.get(FORM_10K, {}).get("net_income") or {}
    c = new_blocks.get(FORM_COMBINED, {}).get("net_income") or {}
    pr = c.get("raw_pearson_r")
    sr = c.get("spearman_rho")
    wr = c.get("winsorized_pearson_r")
    if pr is not None and sr is not None and abs(pr - sr) < 0.15:
        tags.append("pearson_spearman_agree")
    if pr is not None and sr is not None and abs(pr) >= 0.4 and abs(sr) < 0.2:
        tags.append("raw_pearson_strong_spearman_weak")
    if pr is not None and wr is not None and abs(pr - wr) >= 0.15:
        tags.append("winsor_changes_pearson")
    if q.get("raw_pearson_r") is not None and k.get("raw_pearson_r") is not None:
        if abs(float(q["raw_pearson_r"]) - float(k["raw_pearson_r"])) >= 0.25:
            tags.append("form_separation_matters")
    elif q.get("raw_pearson_r") is not None and old_r is not None:
        if abs(float(q["raw_pearson_r"]) - float(old_r)) >= 0.15 and int(k.get("n") or 0) < 4:
            tags.append("form_separation_matters")
    n_legacy = int(c.get("n") or 0)
    if old_r is not None and n_legacy < 6 and abs(float(old_r)) >= 0.5:
        tags.append("impressive_r_small_n_artifact")
    if old_r is not None and pr is not None and abs(float(old_r) - float(pr)) < 1e-9 and n_legacy < 6:
        tags.append("legacy_pooled_small_n")
    return tags


def main() -> int:
    default = ROOT / "backend" / "data" / "audit_company_stats.json"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not path.exists():
        print(f"Missing audit input: {path}")
        print("Export company_stats (with points) to that path first.")
        return 1

    raw_rows = _load_rows(path)
    companies = build_company_stats_from_cloud_rows(raw_rows)
    sectors = build_sector_stats(companies)

    print("=" * 72)
    print("PHASE 2 STATISTICAL INTEGRITY AUDIT")
    print(f"Source: {path}  companies={len(companies)}")
    print(f"Winsorization requires n>={MIN_N_WINSOR} (P1/P99 unstable below that).")
    print("Production rankings NOT replaced — this is diagnostic only.")
    print("=" * 72)

    # Eligibility
    for form in (FORM_COMBINED, FORM_10Q, FORM_10K):
        counts = ranking_eligibility_counts(companies, form=form, metric="net_income")
        print(f"\nEligibility ({form} net income): {counts}")

    # Outliers
    outliers = outlier_report(companies)
    print("\n--- YoY distribution (net income) ---")
    for form, dist in outliers["net_income_yoy"].items():
        print(f"{form}: {json.dumps(dist, indent=2)}")
    print("\n--- YoY distribution (revenue) ---")
    for form, dist in outliers["revenue_yoy"].items():
        print(f"{form}: {json.dumps(dist, indent=2)}")
    print("\n--- Top 20 extreme NI YoY ---")
    for e in outliers["top20_extreme_ni_yoy"]:
        print(
            f"  {e['ticker']:6} {e.get('form')}  yoy={_fmt(e['raw_yoy'])}  "
            f"sent={_fmt(e['sentiment'])}  flags={e.get('flags')}"
        )

    # Company BEFORE/AFTER
    print("\n" + "=" * 72)
    print("COMPANY BEFORE (legacy pooled Pearson) vs AFTER (Phase 2)")
    print("=" * 72)
    failure_buckets: dict[str, list[str]] = defaultdict(list)
    for c in _pick_companies(companies):
        legacy = summarize(c.get("points") or [])
        old = legacy["correlation"]["net_income"] or {}
        old_r = c.get("cloud_r_income", old.get("r"))
        print(f"\n### {c['ticker']} — {c.get('name')} ({c.get('sector')})")
        print(
            f"OLD pooled: r={_fmt(old_r)}  n={c.get('cloud_n_income') or old.get('n')}  "
            f"p={_fmt(old.get('p_value'))}"
        )
        by_form = (c.get("stats_phase2") or {}).get("by_form") or {}
        for form in (FORM_10Q, FORM_10K, FORM_COMBINED):
            print(_assoc_line(form, (by_form.get(form) or {}).get("net_income") or {}))
            print(_assoc_line(form + " revenue", (by_form.get(form) or {}).get("revenue") or {}))
        tags = classify_story(float(old_r) if old_r is not None else None, by_form)
        print(f"  TAGS: {tags or ['(none)']}")
        for t in tags:
            failure_buckets[t].append(c["ticker"])

    print("\n--- Failure / diagnostic buckets (companies) ---")
    for k, tickers in sorted(failure_buckets.items()):
        print(f"  {k}: {', '.join(tickers)}")

    # Sector BEFORE/AFTER
    print("\n" + "=" * 72)
    print("SECTOR BEFORE (legacy pooled) vs AFTER (filing-weighted / company-balanced)")
    print("=" * 72)
    for s in sectors:
        print(f"\n### {s['sector']}  companies={s['n_companies']} filings={s['n_filings']}")
        print(f"OLD pooled income r={_fmt(s.get('r_income'))} n={s.get('n_income')}")
        by_form = (s.get("stats_phase2") or {}).get("by_form") or {}
        for form in (FORM_10Q, FORM_10K, FORM_COMBINED):
            block = (by_form.get(form) or {}).get("net_income") or {}
            fw = block.get("filing_weighted") or {}
            cb = block.get("company_balanced") or {}
            fa = block.get("filing_weighted_agreement") or {}
            print(
                f"  {form}: filing-weighted r={_fmt(fw.get('raw_pearson_r'))} "
                f"ρ={_fmt(fw.get('spearman_rho'))} n={fw.get('n')} | "
                f"company-balanced r={_fmt(cb.get('r'))} n_co={cb.get('n_companies')} | "
                f"agree {fa.get('label')}"
            )

    # Agreement sensitivity (pooled filings)
    all_points: list[dict[str, Any]] = []
    for c in companies:
        all_points.extend(c.get("points") or [])
    print("\n--- Agreement threshold sensitivity (all filings, combined NI) ---")
    for row in agreement_sensitivity(all_points, "net_income"):
        mark = " [PRODUCTION]" if row.get("is_production") else ""
        print(
            f"  sent|{row['sentiment_neutral']} yoy|{row['yoy_neutral']}: "
            f"{row.get('label')} rate={_fmt(row.get('rate'))}{mark}"
        )

    # Multiple comparisons diagnostic
    print("\n--- Multiple comparisons (combined NI, n>=6 companies) ---")
    p05 = q05 = eligible = 0
    for c in companies:
        assoc = (((c.get("stats_phase2") or {}).get("by_form") or {}).get(FORM_COMBINED) or {}).get(
            "net_income"
        ) or {}
        if int(assoc.get("n") or 0) < 6:
            continue
        eligible += 1
        p = (assoc.get("raw_pearson") or {}).get("p_value")
        q = assoc.get("fdr_q_value")
        if p is not None and p < 0.05:
            p05 += 1
        if q is not None and q < 0.05:
            q05 += 1
    print(f"  eligible companies: {eligible}")
    print(f"  raw p < 0.05: {p05}")
    print(f"  FDR q < 0.05: {q05}")

    out_path = ROOT / "backend" / "data" / "audit_phase2_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "n_companies": len(companies),
                "eligibility_combined_ni": ranking_eligibility_counts(companies),
                "eligibility_10q_ni": ranking_eligibility_counts(companies, form=FORM_10Q),
                "eligibility_10k_ni": ranking_eligibility_counts(companies, form=FORM_10K),
                "outliers": outliers,
                "failure_buckets": dict(failure_buckets),
                "multiple_comparisons": {"eligible": eligible, "p05": p05, "q05": q05},
                "winsor_min_n": MIN_N_WINSOR,
            },
            indent=2,
            default=str,
        )
    )
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
