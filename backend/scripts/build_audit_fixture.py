"""Build audit fixture from agent-tools MCP dumps if available."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "data" / "audit_company_stats.json"
TOOLS = Path("/Users/user/.cursor/projects/Users-user-Projects-EDGAR-Sentiment/agent-tools")


def try_parse_companies(text: str) -> list[dict]:
    companies: dict[str, dict] = {}
    # Prefer untrusted-data blocks
    for m in re.finditer(
        r"<untrusted-data-[0-9a-f-]+>\s*(\[.*?\])\s*</untrusted-data-[0-9a-f-]+>",
        text,
        flags=re.S,
    ):
        blob = m.group(1)
        if '"points"' not in blob:
            continue
        try:
            rows = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict) and r.get("ticker") and "points" in r:
                    companies[r["ticker"]] = r
    if companies:
        return list(companies.values())

    # Fallback: scan for JSON arrays
    for m in re.finditer(r"\[(\{\"ticker\":.*?\})\]", text, flags=re.S):
        blob = "[" + m.group(1) + "]"
        if '"points"' not in blob:
            continue
        try:
            rows = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict) and r.get("ticker") and "points" in r:
                    companies[r["ticker"]] = r
    return list(companies.values())


def main() -> None:
    found: dict[str, dict] = {}
    if TOOLS.exists():
        for path in TOOLS.glob("*.txt"):
            rows = try_parse_companies(path.read_text(errors="ignore"))
            for r in rows:
                found[r["ticker"]] = r
            if rows:
                print(f"{path.name}: +{len(rows)}")

    # Also scan recent transcript for tool results
    transcripts = Path(
        "/Users/user/.cursor/projects/Users-user-Projects-EDGAR-Sentiment/agent-transcripts"
    )
    if transcripts.exists():
        for path in transcripts.rglob("*.jsonl"):
            text = path.read_text(errors="ignore")
            if "income_pct" not in text:
                continue
            rows = try_parse_companies(text)
            for r in rows:
                found[r["ticker"]] = r
            # Also parse escaped JSON inside jsonl tool result strings
            for line in text.splitlines():
                if "income_pct" not in line or "untrusted-data" not in line:
                    continue
                rows = try_parse_companies(line)
                for r in rows:
                    found[r["ticker"]] = r
                # Handle JSON-escaped content
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                dumped = json.dumps(obj)
                rows = try_parse_companies(dumped)
                for r in rows:
                    found[r["ticker"]] = r

    OUT.parent.mkdir(parents=True, exist_ok=True)
    companies = sorted(found.values(), key=lambda r: r["ticker"])
    OUT.write_text(json.dumps({"companies": companies}))
    print(f"wrote {OUT} n={len(companies)} tickers={[c['ticker'] for c in companies]}")


if __name__ == "__main__":
    main()
