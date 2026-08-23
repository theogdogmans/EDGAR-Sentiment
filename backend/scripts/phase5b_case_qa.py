#!/usr/bin/env python3
"""QA: expected Phase 4 case-study values vs Phase 5A preview + optional frontend helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREVIEW = ROOT / "backend" / "data" / "phase5" / "supabase_payload_preview" / "companies.json"

EXPECTED = {
    "AAPL": {"n": 15, "rho": 0.8535714285714284, "r": 0.7660646615554488, "q": 0.01944217593875049, "fdr": True},
    "ADI": {"n": 15, "rho": 0.7749999999999999, "r": 0.765248013948109, "q": 0.01944217593875049, "fdr": True},
    "AMZN": {"n": 15, "rho": -0.5249999999999999, "r": -0.6143639425060876, "q": 0.10464971428484149, "fdr": False},
    "MSFT": {"n": 15, "rho": 0.4357142857142856, "r": 0.5683084748605436, "q": 0.15895710168821373, "fdr": False},
    "NVDA": {"n": 15, "agree": "13 / 13", "fdr": False},
    "ABBV": {"near_zero": True, "fdr": False},
    "ADSK": {"near_zero": True, "fdr": False},
}


def main() -> int:
    if not PREVIEW.exists():
        print("FAIL: preview companies.json missing")
        return 1
    by = {c["ticker"]: c for c in json.loads(PREVIEW.read_text(encoding="utf-8"))}
    errors: list[str] = []
    shown: dict[str, dict] = {}
    for t, exp in EXPECTED.items():
        c = by.get(t)
        if not c:
            errors.append(f"{t}: missing")
            continue
        ni = c.get("primary_10q_ni") or {}
        # Fail if only legacy pooled fields differ but Phase 5 missing
        if c.get("spearman_rho_10q_ni") is None and ni.get("spearman_rho") is None:
            errors.append(f"{t}: missing Phase 5A spearman fields (legacy-only?)")
        row = {
            "n": ni.get("n"),
            "rho": ni.get("spearman_rho"),
            "r": ni.get("pearson_r"),
            "q": ni.get("fdr_q"),
            "fdr": c.get("fdr_significant"),
            "agree": ni.get("agreement_label"),
        }
        shown[t] = row
        if "n" in exp and row["n"] != exp["n"]:
            errors.append(f"{t}: n {row['n']} != {exp['n']}")
        if "rho" in exp and abs(float(row["rho"]) - float(exp["rho"])) > 1e-9:
            errors.append(f"{t}: rho mismatch")
        if "r" in exp and abs(float(row["r"]) - float(exp["r"])) > 1e-9:
            errors.append(f"{t}: r mismatch")
        if "q" in exp and abs(float(row["q"]) - float(exp["q"])) > 1e-9:
            errors.append(f"{t}: q mismatch")
        if "fdr" in exp and bool(row["fdr"]) != bool(exp["fdr"]):
            errors.append(f"{t}: fdr {row['fdr']} != {exp['fdr']}")
        if "agree" in exp and row["agree"] != exp["agree"]:
            errors.append(f"{t}: agree {row['agree']} != {exp['agree']}")
        if exp.get("near_zero") and abs(float(row["r"] or 99)) >= 0.15:
            errors.append(f"{t}: expected near-zero r, got {row['r']}")
    print(json.dumps(shown, indent=2))
    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("OK case-study regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
