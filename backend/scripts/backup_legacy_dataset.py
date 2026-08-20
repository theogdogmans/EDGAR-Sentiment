#!/usr/bin/env python3
"""Export legacy cloud company_stats snapshot for Phase 3 comparison.

Does not mutate production data.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "backend" / "data" / "legacy_backup"
ENV_CANDIDATES = [
    ROOT / "frontend" / ".env.local",
    ROOT / ".env",
]


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for path in ENV_CANDIDATES:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> int:
    env = _load_env()
    url = env.get("NEXT_PUBLIC_SUPABASE_URL") or env.get("SUPABASE_URL")
    key = (
        env.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        or env.get("SUPABASE_ANON_KEY")
    )
    if not url or not key:
        print("Missing Supabase URL/key in frontend/.env.local")
        return 1

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    cols = (
        "ticker,display,name,sector,cik,n_filings,mean_sentiment,"
        "r_income,p_income,n_income,r_revenue,p_revenue,n_revenue,"
        "agreement_income,agreement_revenue,points,featured"
    )
    rows: list[dict] = []
    offset = 0
    page = 100
    while True:
        req = urllib.request.Request(
            f"{url}/rest/v1/company_stats?select={cols}&order=ticker&limit={page}&offset={offset}",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            chunk = json.loads(resp.read().decode())
        rows.extend(chunk)
        if len(chunk) < page:
            break
        offset += page

    with_points = [r for r in rows if r.get("points")]
    points = [p for r in with_points for p in (r.get("points") or [])]
    ni = sum(1 for p in points if p.get("income_pct") is not None)
    rev = sum(1 for p in points if p.get("revenue_pct") is not None)
    scored = sum(1 for p in points if p.get("sentiment") is not None)

    summary = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": "supabase.company_stats",
        "n_company_rows": len(rows),
        "n_companies_with_points": len(with_points),
        "n_filings_in_points": len(points),
        "n_sentiment_observations": scored,
        "n_revenue_yoy_pairs": rev,
        "n_net_income_yoy_pairs": ni,
        "n_income_ge_3": sum(1 for r in rows if (r.get("n_income") or 0) >= 3),
        "n_income_ge_6": sum(1 for r in rows if (r.get("n_income") or 0) >= 6),
        "n_income_ge_8": sum(1 for r in rows if (r.get("n_income") or 0) >= 8),
        "n_income_ge_10": sum(1 for r in rows if (r.get("n_income") or 0) >= 10),
        "note": (
            "Legacy cloud aggregates; local SQLite was empty at Phase 3 start. "
            "These observations predate Phase 1 extraction/XBRL corrections."
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    companies_path = OUT_DIR / f"company_stats_{stamp}.json"
    summary_path = OUT_DIR / "legacy_summary.json"
    latest = OUT_DIR / "company_stats_latest.json"
    companies_path.write_text(json.dumps({"summary": summary, "companies": rows}))
    latest.write_text(json.dumps({"summary": summary, "companies": with_points}))
    summary_path.write_text(json.dumps(summary, indent=2))
    # Convenience copy used by audits
    (ROOT / "backend" / "data" / "audit_company_stats.json").write_text(
        json.dumps({"companies": with_points})
    )
    print(json.dumps(summary, indent=2))
    print(f"wrote {companies_path}")
    print(f"wrote {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
