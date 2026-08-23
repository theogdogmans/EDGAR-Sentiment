#!/usr/bin/env python3
"""Validate Phase 5A migration SQL is additive-only (no production execute)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "supabase" / "migrations" / "20260823_phase5a_production_fields.sql"

FORBIDDEN = [
    re.compile(r"\bDROP\s+TABLE\b", re.I),
    re.compile(r"\bDROP\s+COLUMN\b", re.I),
    re.compile(r"\bTRUNCATE\b", re.I),
    re.compile(r"\bDELETE\s+FROM\b", re.I),
    re.compile(r"\bUPDATE\b", re.I),
    re.compile(r"\bALTER\s+TABLE\s+\w+\s+RENAME\b", re.I),
]


def main() -> int:
    text = MIG.read_text(encoding="utf-8")
    errors: list[str] = []
    for pat in FORBIDDEN:
        if pat.search(text):
            errors.append(f"Forbidden pattern: {pat.pattern}")
    if "ADD COLUMN IF NOT EXISTS" not in text:
        errors.append("Expected ADD COLUMN IF NOT EXISTS")
    if "JSONB" not in text.upper():
        errors.append("Expected JSONB types")
    if "DOUBLE PRECISION" not in text.upper():
        errors.append("Expected DOUBLE PRECISION numeric fields")
    if "CREATE INDEX IF NOT EXISTS" not in text.upper():
        errors.append("Expected CREATE INDEX IF NOT EXISTS")
    # Legacy columns must not be dropped (comment presence)
    if "Legacy columns intentionally retained" not in text:
        errors.append("Missing legacy-retention note")
    print("migration_file", MIG)
    print("bytes", len(text.encode("utf-8")))
    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("OK additive-only migration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
