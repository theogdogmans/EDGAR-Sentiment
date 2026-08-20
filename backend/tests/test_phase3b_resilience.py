"""Phase 3B resilience: history shards, CIK dedupe, isolation, skip-completed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Bind tests to a temp Phase 3 DB via env before importing app.config consumers.
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="edgar_phase3b_")
os.environ["PHASE3_DB_NAME"] = "test_phase3b.db"
# Force config path under tmp by monkeypatching after import in fixtures.


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_phase3b.db"
    monkeypatch.setenv("PHASE3_DB_NAME", db_path.name)
    import app.config as config
    import app.db as db

    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    db.replace_sp500(
        [
            {"ticker": "AAPL", "display": "AAPL", "name": "Apple", "sector": "Information Technology"},
            {"ticker": "XOM", "display": "XOM", "name": "Exxon", "sector": "Energy"},
            {"ticker": "GOOGL", "display": "GOOGL", "name": "Alphabet A", "sector": "Communication Services"},
            {"ticker": "GOOG", "display": "GOOG", "name": "Alphabet C", "sector": "Communication Services"},
            {"ticker": "FOX", "display": "FOX", "name": "Fox B", "sector": "Communication Services"},
            {"ticker": "FOXA", "display": "FOXA", "name": "Fox A", "sector": "Communication Services"},
        ]
    )

    def _noop_refresh(force: bool = False):
        return [dict(r) for r in db.list_sp500()]

    monkeypatch.setattr("app.sp500.refresh_sp500", _noop_refresh)
    monkeypatch.setattr("app.registrants.refresh_sp500", _noop_refresh)
    monkeypatch.setattr(db, "sp500_count", lambda: 500)
    yield db


def _block(forms, accessions, filed, docs=None):
    docs = docs or [f"{a}.htm" for a in accessions]
    return {
        "form": forms,
        "accessionNumber": accessions,
        "filingDate": filed,
        "reportDate": filed,
        "primaryDocument": docs,
    }


def test_historical_filings_files_traversal_and_dedupe(isolated_db):
    from app.edgar.client import collect_10k_10q_for_cik

    recent = _block(
        ["10-Q", "8-K", "10-K"],
        ["0000320193-25-000001", "0000320193-25-000002", "0000320193-25-000003"],
        ["2025-01-01", "2025-01-02", "2024-11-01"],
    )
    # Shard has overlapping accession + older 10-Qs to fill toward 20
    shard_forms = ["10-Q"] * 18 + ["10-K"]
    shard_acc = [f"0000320193-20-{i:06d}" for i in range(19)]
    shard_acc[0] = "0000320193-25-000001"  # duplicate of recent
    shard_filed = [f"2020-{(i % 12) + 1:02d}-01" for i in range(19)]
    shard = _block(shard_forms, shard_acc, shard_filed)

    submissions = {
        "name": "Apple Inc.",
        "filings": {
            "recent": recent,
            "files": [{"name": "CIK0000320193-submissions-001.json", "filingCount": 19}],
        },
    }

    def fake_fetch(url, headers, **kwargs):
        if url.endswith("CIK0000320193.json"):
            return submissions
        if "submissions-001" in url:
            return shard
        raise AssertionError(url)

    with patch("app.edgar.client.fetch_json", side_effect=fake_fetch):
        rows = collect_10k_10q_for_cik("0000320193", ticker="AAPL", limit=20)

    accs = [r["accession"] for r in rows]
    assert len(accs) == len(set(accs))
    assert len(rows) == 20
    assert rows[0].get("_used_archive_shard") is True
    assert all(r["form"] in ("10-K", "10-Q") for r in rows)
    # Newest first
    dates = [r["filed"] for r in rows]
    assert dates == sorted(dates, reverse=True)


def test_max_20_filing_limit(isolated_db):
    from app.edgar.client import collect_10k_10q_for_cik

    forms = ["10-Q"] * 30
    accs = [f"0000320193-25-{i:06d}" for i in range(30)]
    filed = [f"2025-01-{(i % 28) + 1:02d}" for i in range(30)]
    submissions = {
        "name": "Apple",
        "filings": {"recent": _block(forms, accs, filed), "files": []},
    }
    with patch("app.edgar.client.fetch_json", return_value=submissions):
        rows = collect_10k_10q_for_cik("0000320193", ticker="AAPL", limit=20)
    assert len(rows) == 20


def test_accession_prefix_cik_recovery_for_thin_history(isolated_db):
    """XOM-like: mapped CIK has 1 filing whose accession prefix is the real filer."""
    from app.edgar.client import resolve_ticker

    thin = {
        "name": "ExxonMobil Holdings Corp",
        "filings": {
            "recent": _block(
                ["10-Q"],
                ["0000034088-26-000093"],
                ["2026-08-03"],
            ),
            "files": [],
        },
    }
    rich_forms = ["10-Q"] * 15 + ["10-K"] * 5
    rich_acc = [f"0000034088-25-{i:06d}" for i in range(20)]
    rich_filed = [f"2024-{(i % 12) + 1:02d}-15" for i in range(20)]
    rich = {
        "name": "EXXON MOBIL CORP",
        "filings": {"recent": _block(rich_forms, rich_acc, rich_filed), "files": []},
    }

    def fake_fetch(url, headers, **kwargs):
        if "CIK0002115436" in url:
            return thin
        if "CIK0000034088" in url:
            return rich
        raise AssertionError(url)

    tickers = [
        {"ticker": "XOM", "cik": "0002115436", "name": "ExxonMobil Holdings Corp"},
        {"ticker": "AAPL", "cik": "0000320193", "name": "Apple"},
    ]
    with patch("app.edgar.client.load_tickers", return_value=tickers), patch(
        "app.edgar.client.fetch_json", side_effect=fake_fetch
    ):
        company = resolve_ticker("XOM", validate_history=True)
    assert company["cik"] == "0000034088"
    assert company["cik_resolution"].startswith("accession_prefix")


def test_multiple_ticker_classes_share_one_cik(isolated_db):
    from app.registrants import duplicate_cik_groups, registrant_plan

    mapping = {
        "GOOGL": "0001652044",
        "GOOG": "0001652044",
        "FOX": "0001754301",
        "FOXA": "0001754301",
        "AAPL": "0000320193",
    }
    with patch("app.registrants.map_tickers_to_ciks", return_value=mapping):
        groups = duplicate_cik_groups(mapping)
        plan = registrant_plan(["GOOGL", "GOOG", "FOX", "FOXA", "AAPL"])
    assert len(groups) == 2
    goog = next(g for g in groups if g["cik"] == "0001652044")
    assert set(goog["tickers"]) == {"GOOG", "GOOGL"}
    assert goog["canonical_ticker"] == "GOOGL"  # PRIORITY
    canons = [p["canonical_ticker"] for p in plan]
    assert canons.count("GOOGL") == 1
    assert "GOOG" not in canons
    assert len(plan) == 3  # Alphabet, Fox, Apple


def test_retry_limit_and_failed_filing_does_not_stop_company(isolated_db, monkeypatch):
    from app import db
    from app.phase3_rebuild import analyze_filing_with_log, rebuild_company

    monkeypatch.setattr("app.phase3_rebuild.FILING_MAX_ATTEMPTS", 2)
    monkeypatch.setattr("app.phase3_rebuild.FILING_SOFT_TIMEOUT_S", 30)

    filings = [
        {
            "accession": "0000320193-25-000001",
            "ticker": "AAPL",
            "cik": "0000320193",
            "form": "10-Q",
            "filed": "2025-01-01",
            "report_date": "2024-12-31",
            "primary_doc": "a.htm",
            "filing_url": "https://example.com/a.htm",
        },
        {
            "accession": "0000320193-25-000002",
            "ticker": "AAPL",
            "cik": "0000320193",
            "form": "10-Q",
            "filed": "2024-10-01",
            "report_date": "2024-09-30",
            "primary_doc": "b.htm",
            "filing_url": "https://example.com/b.htm",
        },
    ]
    db.upsert_company("AAPL", "0000320193", "Apple")
    db.upsert_filings(filings)

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise TimeoutError("simulated timeout")

    with patch("app.phase3_rebuild.download_filing_html", side_effect=boom), patch(
        "app.phase3_rebuild.resolve_ticker",
        return_value={"ticker": "AAPL", "cik": "0000320193", "name": "Apple"},
    ), patch("app.phase3_rebuild.list_recent_filings", return_value=filings), patch(
        "app.phase3_rebuild.load_company_facts", return_value={}
    ):
        # First filing fails (retryable then final across attempts inside analyze)
        out1 = analyze_filing_with_log("0000320193-25-000001", skip_completed=False)
        assert out1["ok"] is False
        job = db.get_filing_job("0000320193-25-000001")
        assert job["status"] in (db.JOB_FAILED_RETRYABLE, db.JOB_FAILED_FINAL)
        # Second attempt pushes to final
        out1b = analyze_filing_with_log("0000320193-25-000001", skip_completed=False)
        assert out1b["ok"] is False
        job = db.get_filing_job("0000320193-25-000001")
        assert job["status"] == db.JOB_FAILED_FINAL
        assert job["attempts"] >= 2

        summary = rebuild_company("AAPL", force_filings=False, force_analyze=True, skip_completed=False)
        assert summary["company_failed"] is False
        assert summary["filings_attempted"] == 2


def test_failed_company_does_not_stop_rebuild(isolated_db):
    from app.phase3_rebuild import rebuild_company

    with patch(
        "app.phase3_rebuild.resolve_ticker",
        side_effect=RuntimeError("SEC down"),
    ):
        a = rebuild_company("AAPL")
    assert a["company_failed"] is True
    with patch(
        "app.phase3_rebuild.resolve_ticker",
        return_value={"ticker": "XOM", "cik": "0000034088", "name": "XOM"},
    ), patch("app.phase3_rebuild.list_recent_filings", return_value=[]), patch(
        "app.phase3_rebuild.load_company_facts", return_value={}
    ):
        b = rebuild_company("XOM")
    assert b["company_failed"] is False
    assert b["filings_attempted"] == 0


def test_skip_completed_does_not_rerun_finbert(isolated_db):
    from app import db
    from app.phase3_rebuild import analyze_filing_with_log

    acc = "0000320193-25-000099"
    db.upsert_company("AAPL", "0000320193", "Apple")
    db.upsert_filings(
        [
            {
                "accession": acc,
                "ticker": "AAPL",
                "cik": "0000320193",
                "form": "10-Q",
                "filed": "2025-01-01",
                "report_date": "2024-12-31",
                "primary_doc": "a.htm",
                "filing_url": "https://example.com/a.htm",
            }
        ]
    )
    db.set_analysis(
        {
            "accession": acc,
            "sentiment_score": 0.1,
            "positive_share": 0.4,
            "negative_share": 0.3,
            "neutral_share": 0.3,
            "sentence_count": 10,
            "sentences_json": "[]",
            "metrics_json": json.dumps(
                {
                    "net_income": {"status": "ok", "pct_change": 0.1},
                    "revenue": {"status": "ok", "pct_change": 0.05},
                }
            ),
            "agreement_income": 1,
            "agreement_revenue": 1,
        }
    )
    with patch("app.phase3_rebuild.analyze_text") as finbert, patch(
        "app.phase3_rebuild.download_filing_html"
    ) as dl:
        out = analyze_filing_with_log(acc, force=False, skip_completed=True)
    assert out["ok"] is True
    assert out.get("skipped") is True
    finbert.assert_not_called()
    dl.assert_not_called()
    job = db.get_filing_job(acc)
    assert job["status"] == db.JOB_COMPLETE


def test_filing_url_uses_registrant_cik_not_accession_prefix(isolated_db):
    """Filing-agent accession prefixes must not drive archive paths."""
    from app.edgar.client import collect_10k_10q_for_cik

    submissions = {
        "name": "Arthur J. Gallagher & Co.",
        "filings": {
            "recent": _block(
                ["10-Q"],
                ["0001628280-26-053489"],
                ["2026-08-01"],
                docs=["ajg-20260630.htm"],
            ),
            "files": [],
        },
    }
    with patch("app.edgar.client.fetch_json", return_value=submissions):
        rows = collect_10k_10q_for_cik("0000354190", ticker="AJG", limit=5)
    assert rows[0]["cik"] == "0000354190"
    assert "/edgar/data/354190/" in rows[0]["filing_url"]
    assert "/edgar/data/1628280/" not in rows[0]["filing_url"]


def test_retrieval_ordering_newest_first(isolated_db):
    from app.edgar.client import collect_10k_10q_for_cik

    submissions = {
        "name": "Apple",
        "filings": {
            "recent": _block(
                ["10-Q", "10-Q", "10-K"],
                ["0000320193-25-000003", "0000320193-25-000001", "0000320193-25-000002"],
                ["2023-01-01", "2025-06-01", "2024-01-01"],
            ),
            "files": [],
        },
    }
    with patch("app.edgar.client.fetch_json", return_value=submissions):
        rows = collect_10k_10q_for_cik("0000320193", ticker="AAPL", limit=20)
    assert [r["filed"] for r in rows] == ["2025-06-01", "2024-01-01", "2023-01-01"]
