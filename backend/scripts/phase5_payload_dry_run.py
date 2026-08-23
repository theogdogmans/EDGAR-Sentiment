#!/usr/bin/env python3
"""Phase 5A — serialize production sync payload locally (no Supabase upload)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("PHASE3_DB_NAME", "edgar_phase3.db")

from app.phase5_payload import (  # noqa: E402
    build_full_payload,
    footprint,
    validate_payload,
    verify_case_studies,
)

OUT = ROOT / "backend" / "data" / "phase5" / "supabase_payload_preview"
PHASE4 = ROOT / "backend" / "data" / "phase4" / "phase4_final_report.json"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = build_full_payload()
    companies = payload["companies"]
    sectors = payload["sectors"]
    examples = payload["example_filings"]

    (OUT / "companies.json").write_text(
        json.dumps(companies, indent=2, allow_nan=False, default=str), encoding="utf-8"
    )
    (OUT / "sectors.json").write_text(
        json.dumps(sectors, indent=2, allow_nan=False, default=str), encoding="utf-8"
    )
    (OUT / "example_filings.json").write_text(
        json.dumps(examples, indent=2, allow_nan=False, default=str), encoding="utf-8"
    )

    validation = validate_payload(payload)
    sizes = footprint(payload)

    phase4_cases = None
    phase4_reconcile: dict = {}
    if PHASE4.exists():
        p4 = json.loads(PHASE4.read_text(encoding="utf-8"))
        phase4_cases = p4.get("I_case_studies")
        fdr = p4.get("D_fdr_results") or {}
        elig = p4.get("C_ranking_eligibility") or {}
        phase4_reconcile = {
            "phase4_n_ge_8": elig.get("n_ge_8"),
            "payload_n_ge_8": sizes["n_eligible_n8"],
            "phase4_fdr_q_lt_05": fdr.get("fdr_q_lt_05"),
            "payload_fdr_significant": sizes["n_fdr_q_lt_05"],
            "phase4_analyses": (p4.get("A_dataset_checkpoint") or {}).get("analyses"),
            "payload_chart_points": sizes["chart_points"],
            "n8_match": elig.get("n_ge_8") == sizes["n_eligible_n8"],
            "fdr_match": fdr.get("fdr_q_lt_05") == sizes["n_fdr_q_lt_05"],
        }

    cases = verify_case_studies(payload, phase4_cases)

    # Sector verification snapshot
    sector_verify = [
        {
            "sector": s["sector"],
            "fw_pearson": s.get("fw_pearson_r_10q_ni"),
            "fw_spearman": s.get("fw_spearman_rho_10q_ni"),
            "fw_winsor": s.get("fw_winsor_r_10q_ni"),
            "fw_n": s.get("fw_n_10q_ni"),
            "cb_r": s.get("cb_pearson_r_10q_ni"),
            "cb_n": s.get("cb_n_companies_10q_ni"),
            "revenue_comparable": s.get("revenue_comparable"),
        }
        for s in sectors
    ]

    summary = {
        "upload": False,
        "payload_version": payload["meta"]["payload_version"],
        "built_at": payload["meta"]["built_at"],
        "tables": {
            "company_stats": sizes["company_rows"],
            "sector_stats": sizes["sector_rows"],
            "example_filings": sizes["example_rows"],
            "preload_status": "unchanged (not written in dry-run)",
        },
        "footprint": sizes,
        "validation": validation,
        "phase4_reconcile": phase4_reconcile,
        "case_studies": cases,
        "sectors": sector_verify,
        "featured_roles": payload["meta"]["featured_roles"],
        "alias_excluded_from_sector": payload["meta"]["alias_excluded_from_sector"],
        "live_site_comparison_note": (
            "Live demo (read-only): ~171 chart points, 20 companies with n_income>=3, "
            "pooled legacy r_income. Phase 5A payload: full 9697 points, n>=8 default, "
            "10-Q primary Spearman/Pearson/FDR."
        ),
        "schema_migration_file": "supabase/migrations/20260823_phase5a_production_fields.sql",
        "stop": "DRY RUN COMPLETE — no Supabase upload performed.",
    }

    (OUT / "payload_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False, default=str), encoding="utf-8"
    )
    (OUT / "validation.json").write_text(
        json.dumps(validation, indent=2, default=str), encoding="utf-8"
    )

    print("=" * 72)
    print("PHASE 5A PAYLOAD DRY RUN (no upload)")
    print("=" * 72)
    print(json.dumps(sizes, indent=2))
    print("validation.ok:", validation["ok"])
    if validation["errors"]:
        print("ERRORS:")
        for e in validation["errors"][:20]:
            print(" -", e)
    if validation["warnings"]:
        print("WARNINGS:")
        for w in validation["warnings"]:
            print(" -", w)
    print("phase4_reconcile:", json.dumps(phase4_reconcile, indent=2))
    print("case studies:")
    for row in cases:
        print(
            f"  {row['ticker']}: n={row.get('n')} rho={row.get('spearman_rho')} "
            f"r={row.get('pearson_r')} q={row.get('fdr_q')} fdr={row.get('fdr_significant')} "
            f"agree={row.get('agreement_label')} p4_match={row.get('phase4_match')}"
        )
    print(f"Wrote {OUT}")
    return 0 if validation["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
