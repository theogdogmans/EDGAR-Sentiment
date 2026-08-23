"""Regression tests for Phase 5B sync safety (no network uploads)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app import supabase_sync
from app.phase5_payload import CASE_STUDY_TICKERS, PAYLOAD_VERSION, validate_payload
from app.supabase_sync import _clear_example_filings, push_phase5a


ROOT = Path(__file__).resolve().parents[2]
SYNC_PATH = ROOT / "backend" / "app" / "supabase_sync.py"


def test_example_filings_delete_does_not_use_bare_null():
    """The old `null` NameError must never return."""
    src = SYNC_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "null":
            pytest.fail("Bare name `null` found in supabase_sync.py — use None or PostgREST helpers")
    # Source-level guard for the old bug pattern
    assert 'is", null)' not in src
    assert ".not(\"accession\", \"is\", null)" not in src


def test_clear_example_filings_uses_safe_filter():
    calls: list[tuple] = []

    class FakeQuery:
        def neq(self, col, val):
            calls.append(("neq", col, val))
            return self

        def execute(self):
            calls.append(("execute",))
            return self

    class FakeTable:
        def delete(self):
            calls.append(("delete",))
            return FakeQuery()

    class FakeClient:
        def table(self, name):
            assert name == "example_filings"
            return FakeTable()

    _clear_example_filings(FakeClient())
    assert ("delete",) in calls
    assert ("neq", "accession", "") in calls
    assert ("execute",) in calls


def test_push_phase5a_defaults_to_dry_run_no_upload(monkeypatch):
    """Default must refuse network writes even if Supabase env is present."""

    def boom():
        raise AssertionError("_supabase should not be called on dry_run")

    monkeypatch.setattr(supabase_sync, "_supabase", boom)
    # Avoid rebuilding the full Phase 3 corpus in unit tests if DB missing;
    # stub build_full_payload instead.
    monkeypatch.setattr(
        supabase_sync,
        "build_full_payload",
        lambda: {
            "companies": [{"ticker": "AAPL", "payload_version": PAYLOAD_VERSION}],
            "sectors": [{"sector": "Information Technology"}],
            "example_filings": [],
            "meta": {"payload_version": PAYLOAD_VERSION},
        },
    )
    out = push_phase5a()  # dry_run defaults True
    assert out["dry_run"] is True
    assert out["uploaded"] is False
    assert out["companies"] == 1
    assert "Dry run" in out["message"]


def test_push_phase5a_signature_defaults_dry_run():
    sig = inspect.signature(push_phase5a)
    assert sig.parameters["dry_run"].default is True


def test_phase5_preview_payload_validates_if_present():
    preview = ROOT / "backend" / "data" / "phase5" / "supabase_payload_preview" / "companies.json"
    if not preview.exists():
        pytest.skip("Phase 5A preview not generated yet")
    import json

    companies = json.loads(preview.read_text(encoding="utf-8"))
    sectors = json.loads(preview.with_name("sectors.json").read_text(encoding="utf-8"))
    examples = json.loads(preview.with_name("example_filings.json").read_text(encoding="utf-8"))
    result = validate_payload({"companies": companies, "sectors": sectors, "example_filings": examples})
    assert result["ok"], result["errors"][:10]
    assert result["n_default_rank"] == 440
    assert result["n_fdr_significant"] == 33
    by = {c["ticker"]: c for c in companies}
    for t in CASE_STUDY_TICKERS:
        assert t in by
    aapl = by["AAPL"]["primary_10q_ni"]
    assert abs(float(aapl["spearman_rho"]) - 0.8535714285714284) < 1e-9
    assert abs(float(aapl["pearson_r"]) - 0.7660646615554488) < 1e-9
    assert aapl["n"] == 15
    assert by["AAPL"]["fdr_significant"] is True
    assert by["AMZN"]["fdr_significant"] is False
    assert abs(float(by["AMZN"]["primary_10q_ni"]["pearson_r"]) + 0.6143639425060876) < 1e-9
