#!/usr/bin/env python3
"""Phase 5C: backup live Supabase tables before production release."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

OUT = ROOT / "backend" / "data" / "phase5" / "production_backup"
TABLES = ("company_stats", "sector_stats", "example_filings", "preload_status")


def _client():
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
    from supabase import create_client

    return create_client(url, key)


def _fetch_all(client, table: str) -> list[dict]:
    rows: list[dict] = []
    page = 0
    page_size = 500
    while True:
        start = page * page_size
        end = start + page_size - 1
        resp = client.table(table).select("*").range(start, end).execute()
        batch = resp.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return rows


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = OUT / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    client = _client()
    summary: dict = {"timestamp": ts, "tables": {}}
    for table in TABLES:
        rows = _fetch_all(client, table)
        path = out_dir / f"{table}.json"
        path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
        summary["tables"][table] = {"rows": len(rows), "file": str(path.relative_to(ROOT))}
        print(f"{table}: {len(rows)} rows -> {path.name}")
    (out_dir / "backup_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "latest_backup.txt").write_text(str(out_dir.relative_to(ROOT)), encoding="utf-8")
    print("BACKUP_OK", json.dumps(summary["tables"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
