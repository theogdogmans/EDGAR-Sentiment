#!/usr/bin/env python3
"""Phase 5C: verify production Supabase after Phase 5A upload."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

CASES = {
    "AAPL": {"n": 15, "rho": 0.8535714285714284, "r": 0.7660646615554488, "q": 0.01944217593875049, "fdr": True, "agree": "6 / 8"},
    "ADI": {"n": 15, "rho": 0.7749999999999999, "r": 0.765248013948109, "q": 0.01944217593875049, "fdr": True, "agree": "8 / 8"},
    "AMZN": {"n": 15, "rho": -0.5249999999999999, "r": -0.6143639425060876, "q": 0.10464971428484149, "fdr": False},
    "MSFT": {"n": 15, "rho": 0.4357142857142856, "r": 0.5683084748605436, "q": 0.15895710168821373, "fdr": False},
    "NVDA": {"n": 15, "agree": "13 / 13", "fdr": False},
}


def _client():
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Missing Supabase credentials")
    from supabase import create_client

    return create_client(url, key)


def main() -> int:
    c = _client()
    errors: list[str] = []

    def count(table: str) -> int:
        r = c.table(table).select("*", count="exact").limit(1).execute()
        return int(r.count or 0)

    n_co = count("company_stats")
    n_se = count("sector_stats")
    n_ex = count("example_filings")
    print(f"counts companies={n_co} sectors={n_se} examples={n_ex}")

    if n_co != 502:
        errors.append(f"company_stats expected 502 got {n_co}")
    if n_se != 11:
        errors.append(f"sector_stats expected 11 got {n_se}")

    # chart points + eligibility from full fetch (paginated)
    companies = []
    page = 0
    while True:
        resp = c.table("company_stats").select("ticker,points,n_10q_ni,fdr_significant,ranking_eligible_default,primary_10q_ni,spearman_rho_10q_ni,pearson_r_10q_ni,fdr_q_10q_ni,agreement_num_10q_ni,agreement_den_10q_ni,secondary_10q_revenue,sector").range(page * 500, page * 500 + 499).execute()
        batch = resp.data or []
        companies.extend(batch)
        if len(batch) < 500:
            break
        page += 1

    tickers = [x["ticker"] for x in companies]
    if len(tickers) != len(set(tickers)):
        errors.append("duplicate tickers")

    chart = 0
    accs: set[str] = set()
    dup_acc = False
    eligible = 0
    fdr_n = 0
    fin_rev_ok = 0
    re_rev_ok = 0
    for row in companies:
        pts = row.get("points") or []
        chart += len(pts)
        for p in pts:
            a = p.get("accession")
            if a:
                if a in accs:
                    dup_acc = True
                accs.add(a)
        if row.get("ranking_eligible_default"):
            eligible += 1
        if row.get("fdr_significant"):
            fdr_n += 1
        sec = row.get("sector")
        rev = row.get("secondary_10q_revenue") or {}
        if sec == "Financials" and rev.get("available"):
            fin_rev_ok += 1
        if sec == "Real Estate" and rev.get("available"):
            re_rev_ok += 1
        for key in ("spearman_rho_10q_ni", "pearson_r_10q_ni", "fdr_q_10q_ni"):
            v = row.get(key)
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                errors.append(f"{row['ticker']}: non-finite {key}")

    print(f"chart_points={chart} eligible_n8={eligible} fdr={fdr_n}")
    if chart != 9697:
        errors.append(f"chart points expected 9697 got {chart}")
    if eligible != 440:
        errors.append(f"eligible expected 440 got {eligible}")
    if fdr_n != 33:
        errors.append(f"fdr expected 33 got {fdr_n}")
    if dup_acc:
        errors.append("duplicate accessions in points")
    if fin_rev_ok or re_rev_ok:
        errors.append("Financials/RE revenue leaked as available")

    by = {r["ticker"]: r for r in companies}
    for t, exp in CASES.items():
        row = by.get(t)
        if not row:
            errors.append(f"{t} missing")
            continue
        ni = row.get("primary_10q_ni") or {}
        rho = row.get("spearman_rho_10q_ni") or ni.get("spearman_rho")
        r = row.get("pearson_r_10q_ni") or ni.get("pearson_r")
        q = row.get("fdr_q_10q_ni") or ni.get("fdr_q")
        n = row.get("n_10q_ni") or ni.get("n")
        agree = ni.get("agreement_label")
        print(f"{t} n={n} rho={rho} r={r} q={q} fdr={row.get('fdr_significant')} agree={agree}")
        if n != exp.get("n"):
            errors.append(f"{t} n mismatch")
        if "rho" in exp and abs(float(rho) - exp["rho"]) > 1e-6:
            errors.append(f"{t} rho mismatch")
        if "r" in exp and abs(float(r) - exp["r"]) > 1e-6:
            errors.append(f"{t} r mismatch")
        if "q" in exp and abs(float(q) - exp["q"]) > 1e-6:
            errors.append(f"{t} q mismatch")
        if row.get("fdr_significant") != exp.get("fdr"):
            errors.append(f"{t} fdr mismatch")
        if "agree" in exp and agree != exp["agree"]:
            errors.append(f"{t} agree mismatch {agree}")

    for t in ("ABBV", "ADSK"):
        row = by.get(t)
        if row:
            r = row.get("pearson_r_10q_ni") or (row.get("primary_10q_ni") or {}).get("pearson_r")
            if r is not None and abs(float(r)) >= 0.15:
                errors.append(f"{t} not near-zero r={r}")

    result = {"ok": not errors, "errors": errors, "counts": {"companies": n_co, "sectors": n_se, "examples": n_ex, "chart": chart, "eligible": eligible, "fdr": fdr_n}}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
