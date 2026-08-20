import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from .config import DB_PATH


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS companies (
                ticker TEXT PRIMARY KEY,
                cik TEXT NOT NULL,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS filings (
                accession TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                cik TEXT NOT NULL,
                form TEXT NOT NULL,
                filed TEXT NOT NULL,
                report_date TEXT,
                primary_doc TEXT,
                filing_url TEXT
            );

            CREATE TABLE IF NOT EXISTS mda (
                accession TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                source TEXT NOT NULL,
                start_heading TEXT,
                end_heading TEXT,
                status TEXT,
                confidence TEXT
            );

            CREATE TABLE IF NOT EXISTS analyses (
                accession TEXT PRIMARY KEY,
                sentiment_score REAL NOT NULL,
                positive_share REAL NOT NULL,
                negative_share REAL NOT NULL,
                neutral_share REAL NOT NULL,
                sentence_count INTEGER NOT NULL,
                sentences_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                agreement_income INTEGER,
                agreement_revenue INTEGER
            );

            CREATE TABLE IF NOT EXISTS facts_raw (
                cik TEXT PRIMARY KEY,
                json TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sp500 (
                ticker TEXT PRIMARY KEY,
                display TEXT NOT NULL,
                name TEXT NOT NULL,
                sector TEXT
            );

            -- Phase 2 statistical snapshots (never mutate analyses.metrics_json).
            CREATE TABLE IF NOT EXISTS phase2_company_stats (
                ticker TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                computed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS phase2_sector_stats (
                sector TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                computed_at TEXT NOT NULL
            );

            -- Phase 3: one row per attempted filing (success or failure).
            CREATE TABLE IF NOT EXISTS quality_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                accession TEXT NOT NULL,
                form TEXT,
                filed TEXT,
                report_date TEXT,
                extraction_ok INTEGER,
                extraction_source TEXT,
                mda_chars INTEGER,
                start_heading TEXT,
                end_heading TEXT,
                extraction_status TEXT,
                extraction_confidence TEXT,
                sentence_count INTEGER,
                sentiment_score REAL,
                revenue_status TEXT,
                revenue_tag TEXT,
                revenue_duration REAL,
                revenue_yoy REAL,
                ni_status TEXT,
                ni_tag TEXT,
                ni_duration REAL,
                ni_yoy REAL,
                failure_reason TEXT,
                flags_json TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(accession)
            );

            CREATE INDEX IF NOT EXISTS quality_log_ticker_idx ON quality_log(ticker);

            -- Phase 3B: filing-level checkpoint / resume statuses.
            CREATE TABLE IF NOT EXISTS filing_jobs (
                accession TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                cik TEXT NOT NULL,
                form TEXT,
                status TEXT NOT NULL,
                stage TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                elapsed_s REAL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS filing_jobs_ticker_idx ON filing_jobs(ticker);
            CREATE INDEX IF NOT EXISTS filing_jobs_status_idx ON filing_jobs(status);
            """
        )
        # Migrate older mda tables that lack extraction metadata columns.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(mda)").fetchall()}
        for col, decl in (
            ("start_heading", "TEXT"),
            ("end_heading", "TEXT"),
            ("status", "TEXT"),
            ("confidence", "TEXT"),
        ):
            if col not in cols:
                conn.execute(f"ALTER TABLE mda ADD COLUMN {col} {decl}")

        # Ensure quality_log exists on DBs created before Phase 3.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quality_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                accession TEXT NOT NULL,
                form TEXT,
                filed TEXT,
                report_date TEXT,
                extraction_ok INTEGER,
                extraction_source TEXT,
                mda_chars INTEGER,
                start_heading TEXT,
                end_heading TEXT,
                extraction_status TEXT,
                extraction_confidence TEXT,
                sentence_count INTEGER,
                sentiment_score REAL,
                revenue_status TEXT,
                revenue_tag TEXT,
                revenue_duration REAL,
                revenue_yoy REAL,
                ni_status TEXT,
                ni_tag TEXT,
                ni_duration REAL,
                ni_yoy REAL,
                failure_reason TEXT,
                flags_json TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(accession)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS quality_log_ticker_idx ON quality_log(ticker)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS filing_jobs (
                accession TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                cik TEXT NOT NULL,
                form TEXT,
                status TEXT NOT NULL,
                stage TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                elapsed_s REAL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS filing_jobs_ticker_idx ON filing_jobs(ticker)")
        conn.execute("CREATE INDEX IF NOT EXISTS filing_jobs_status_idx ON filing_jobs(status)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS phase2_company_stats (
                ticker TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                computed_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS phase2_sector_stats (
                sector TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                computed_at TEXT NOT NULL
            )
            """
        )


def meta_get(key: str) -> Optional[str]:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else row["value"]


def meta_set(key: str, value: str, fetched_at: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO meta(key, value, fetched_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, fetched_at=excluded.fetched_at",
            (key, value, fetched_at),
        )


def upsert_company(ticker: str, cik: str, name: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO companies(ticker, cik, name) VALUES(?,?,?) "
            "ON CONFLICT(ticker) DO UPDATE SET cik=excluded.cik, name=excluded.name",
            (ticker.upper(), cik, name),
        )


def get_company(ticker: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM companies WHERE ticker = ?", (ticker.upper(),)
        ).fetchone()


def upsert_filings(rows: list[dict[str, Any]]) -> None:
    with get_db() as conn:
        conn.executemany(
            """
            INSERT INTO filings(accession, ticker, cik, form, filed, report_date, primary_doc, filing_url)
            VALUES(:accession, :ticker, :cik, :form, :filed, :report_date, :primary_doc, :filing_url)
            ON CONFLICT(accession) DO UPDATE SET
                ticker=excluded.ticker,
                form=excluded.form,
                filed=excluded.filed,
                report_date=excluded.report_date,
                primary_doc=excluded.primary_doc,
                filing_url=excluded.filing_url
            """,
            rows,
        )


def list_filings(ticker: str) -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM filings WHERE ticker = ? ORDER BY filed DESC",
            (ticker.upper(),),
        ).fetchall()


def delete_filings_for_ticker(ticker: str) -> int:
    """Remove filing rows for a ticker (analyses/mda keyed by accession are kept)."""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM filings WHERE ticker = ?", (ticker.upper(),))
        return int(cur.rowcount)


def get_filing(accession: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM filings WHERE accession = ?", (accession,)
        ).fetchone()


def get_mda(accession: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM mda WHERE accession = ?", (accession,)).fetchone()


def set_mda(
    accession: str,
    text: str,
    source: str,
    *,
    start_heading: str = "",
    end_heading: str = "",
    status: str = "ok",
    confidence: str = "unknown",
) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO mda(accession, text, source, start_heading, end_heading, status, confidence)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(accession) DO UPDATE SET
                text=excluded.text,
                source=excluded.source,
                start_heading=excluded.start_heading,
                end_heading=excluded.end_heading,
                status=excluded.status,
                confidence=excluded.confidence
            """,
            (accession, text, source, start_heading, end_heading, status, confidence),
        )


def get_analysis(accession: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM analyses WHERE accession = ?", (accession,)
        ).fetchone()


def set_analysis(row: dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO analyses(
                accession, sentiment_score, positive_share, negative_share, neutral_share,
                sentence_count, sentences_json, metrics_json, agreement_income, agreement_revenue
            ) VALUES(
                :accession, :sentiment_score, :positive_share, :negative_share, :neutral_share,
                :sentence_count, :sentences_json, :metrics_json, :agreement_income, :agreement_revenue
            )
            ON CONFLICT(accession) DO UPDATE SET
                sentiment_score=excluded.sentiment_score,
                positive_share=excluded.positive_share,
                negative_share=excluded.negative_share,
                neutral_share=excluded.neutral_share,
                sentence_count=excluded.sentence_count,
                sentences_json=excluded.sentences_json,
                metrics_json=excluded.metrics_json,
                agreement_income=excluded.agreement_income,
                agreement_revenue=excluded.agreement_revenue
            """,
            row,
        )


def get_facts_raw(cik: str) -> Optional[str]:
    with get_db() as conn:
        row = conn.execute("SELECT json FROM facts_raw WHERE cik = ?", (cik,)).fetchone()
        return None if row is None else row["json"]


def set_facts_raw(cik: str, payload: str, fetched_at: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO facts_raw(cik, json, fetched_at) VALUES(?,?,?) "
            "ON CONFLICT(cik) DO UPDATE SET json=excluded.json, fetched_at=excluded.fetched_at",
            (cik, payload, fetched_at),
        )


def replace_sp500(rows: list[dict[str, Any]]) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM sp500")
        conn.executemany(
            "INSERT INTO sp500(ticker, display, name, sector) VALUES(:ticker, :display, :name, :sector)",
            rows,
        )


def is_sp500(ticker: str) -> bool:
    return get_sp500(ticker) is not None


def get_sp500(ticker: str) -> Optional[sqlite3.Row]:
    t = ticker.strip().upper()
    alts = list(dict.fromkeys([t, t.replace(".", "-"), t.replace("-", ".")]))
    with get_db() as conn:
        placeholders = ",".join("?" * len(alts))
        return conn.execute(
            f"SELECT * FROM sp500 WHERE ticker IN ({placeholders}) OR display IN ({placeholders})",
            [*alts, *alts],
        ).fetchone()


def sp500_count() -> int:
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM sp500").fetchone()
        return int(row["n"]) if row else 0


def list_sp500() -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            """
            SELECT
                s.ticker,
                s.display,
                s.name,
                s.sector,
                c.cik,
                COUNT(DISTINCT f.accession) AS filings,
                COUNT(DISTINCT a.accession) AS analyzed
            FROM sp500 s
            LEFT JOIN companies c ON c.ticker = s.ticker
            LEFT JOIN filings f ON f.ticker = s.ticker
            LEFT JOIN analyses a ON a.accession = f.accession
            GROUP BY s.ticker, s.display, s.name, s.sector, c.cik
            ORDER BY s.ticker
            """
        ).fetchall()


def coverage() -> dict[str, int]:
    with get_db() as conn:
        companies = conn.execute("SELECT COUNT(*) AS n FROM sp500").fetchone()["n"]
        with_filings = conn.execute(
            "SELECT COUNT(DISTINCT ticker) AS n FROM filings WHERE ticker IN (SELECT ticker FROM sp500)"
        ).fetchone()["n"]
        filing_n = conn.execute(
            "SELECT COUNT(*) AS n FROM filings WHERE ticker IN (SELECT ticker FROM sp500)"
        ).fetchone()["n"]
        analyzed_n = conn.execute(
            """
            SELECT COUNT(*) AS n FROM analyses
            WHERE accession IN (SELECT accession FROM filings WHERE ticker IN (SELECT ticker FROM sp500))
            """
        ).fetchone()["n"]
        ready = conn.execute(
            """
            SELECT COUNT(*) AS n FROM (
                SELECT s.ticker
                FROM sp500 s
                LEFT JOIN filings f ON f.ticker = s.ticker
                LEFT JOIN analyses a ON a.accession = f.accession
                GROUP BY s.ticker
                HAVING COUNT(DISTINCT a.accession) >= 3
            )
            """
        ).fetchone()["n"]
    return {
        "companies": int(companies),
        "with_filings": int(with_filings),
        "filings": int(filing_n),
        "analyzed": int(analyzed_n),
        "ready": int(ready),
    }


def list_all_filings() -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM filings ORDER BY ticker, filed DESC"
        ).fetchall()


def analysis_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "sentiment": {
            "score": row["sentiment_score"],
            "positive_share": row["positive_share"],
            "negative_share": row["negative_share"],
            "neutral_share": row["neutral_share"],
            "sentence_count": row["sentence_count"],
        },
        "metrics": json.loads(row["metrics_json"]),
        "agreement": {
            "net_income": None if row["agreement_income"] is None else bool(row["agreement_income"]),
            "revenue": None if row["agreement_revenue"] is None else bool(row["agreement_revenue"]),
        },
        "sentences": json.loads(row["sentences_json"]),
    }


def save_phase2_company_stats(rows: list[dict[str, Any]], computed_at: str) -> None:
    """Persist Phase 2 company payloads without touching raw analyses."""
    with get_db() as conn:
        conn.execute("DELETE FROM phase2_company_stats")
        conn.executemany(
            "INSERT INTO phase2_company_stats(ticker, payload_json, computed_at) VALUES(?,?,?)",
            [(r["ticker"], json.dumps(r), computed_at) for r in rows],
        )


def save_phase2_sector_stats(rows: list[dict[str, Any]], computed_at: str) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM phase2_sector_stats")
        conn.executemany(
            "INSERT INTO phase2_sector_stats(sector, payload_json, computed_at) VALUES(?,?,?)",
            [(r["sector"], json.dumps(r), computed_at) for r in rows],
        )


def upsert_quality_log(row: dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO quality_log(
                ticker, accession, form, filed, report_date,
                extraction_ok, extraction_source, mda_chars, start_heading, end_heading,
                extraction_status, extraction_confidence, sentence_count, sentiment_score,
                revenue_status, revenue_tag, revenue_duration, revenue_yoy,
                ni_status, ni_tag, ni_duration, ni_yoy,
                failure_reason, flags_json, created_at
            ) VALUES (
                :ticker, :accession, :form, :filed, :report_date,
                :extraction_ok, :extraction_source, :mda_chars, :start_heading, :end_heading,
                :extraction_status, :extraction_confidence, :sentence_count, :sentiment_score,
                :revenue_status, :revenue_tag, :revenue_duration, :revenue_yoy,
                :ni_status, :ni_tag, :ni_duration, :ni_yoy,
                :failure_reason, :flags_json, :created_at
            )
            ON CONFLICT(accession) DO UPDATE SET
                ticker=excluded.ticker,
                form=excluded.form,
                filed=excluded.filed,
                report_date=excluded.report_date,
                extraction_ok=excluded.extraction_ok,
                extraction_source=excluded.extraction_source,
                mda_chars=excluded.mda_chars,
                start_heading=excluded.start_heading,
                end_heading=excluded.end_heading,
                extraction_status=excluded.extraction_status,
                extraction_confidence=excluded.extraction_confidence,
                sentence_count=excluded.sentence_count,
                sentiment_score=excluded.sentiment_score,
                revenue_status=excluded.revenue_status,
                revenue_tag=excluded.revenue_tag,
                revenue_duration=excluded.revenue_duration,
                revenue_yoy=excluded.revenue_yoy,
                ni_status=excluded.ni_status,
                ni_tag=excluded.ni_tag,
                ni_duration=excluded.ni_duration,
                ni_yoy=excluded.ni_yoy,
                failure_reason=excluded.failure_reason,
                flags_json=excluded.flags_json,
                created_at=excluded.created_at
            """,
            row,
        )


def list_quality_logs() -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM quality_log ORDER BY ticker, filed DESC").fetchall()


def quality_log_counts() -> dict[str, int]:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM quality_log").fetchone()["n"]
        ok = conn.execute(
            "SELECT COUNT(*) AS n FROM quality_log WHERE extraction_ok = 1 AND sentiment_score IS NOT NULL"
        ).fetchone()["n"]
        rev = conn.execute(
            "SELECT COUNT(*) AS n FROM quality_log WHERE revenue_status = 'ok'"
        ).fetchone()["n"]
        ni = conn.execute(
            "SELECT COUNT(*) AS n FROM quality_log WHERE ni_status = 'ok'"
        ).fetchone()["n"]
    return {"attempted": int(total), "scored": int(ok), "revenue_ok": int(rev), "ni_ok": int(ni)}


# --- filing_jobs (Phase 3B checkpoint / resume) ---------------------------------

JOB_PENDING = "pending"
JOB_PROCESSING = "processing"
JOB_COMPLETE = "complete"
JOB_FAILED_RETRYABLE = "failed_retryable"
JOB_FAILED_FINAL = "failed_final"


def upsert_filing_job(row: dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO filing_jobs(
                accession, ticker, cik, form, status, stage, attempts, last_error, elapsed_s, updated_at
            ) VALUES (
                :accession, :ticker, :cik, :form, :status, :stage, :attempts, :last_error, :elapsed_s, :updated_at
            )
            ON CONFLICT(accession) DO UPDATE SET
                ticker=excluded.ticker,
                cik=excluded.cik,
                form=excluded.form,
                status=excluded.status,
                stage=excluded.stage,
                attempts=excluded.attempts,
                last_error=excluded.last_error,
                elapsed_s=excluded.elapsed_s,
                updated_at=excluded.updated_at
            """,
            row,
        )


def get_filing_job(accession: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM filing_jobs WHERE accession = ?", (accession,)
        ).fetchone()


def list_filing_jobs(
    *, ticker: Optional[str] = None, status: Optional[str] = None
) -> list[sqlite3.Row]:
    with get_db() as conn:
        clauses: list[str] = []
        args: list[Any] = []
        if ticker:
            clauses.append("ticker = ?")
            args.append(ticker.upper())
        if status:
            clauses.append("status = ?")
            args.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return conn.execute(
            f"SELECT * FROM filing_jobs{where} ORDER BY updated_at DESC", args
        ).fetchall()


def filing_job_status_counts() -> dict[str, int]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM filing_jobs GROUP BY status"
        ).fetchall()
    return {r["status"]: int(r["n"]) for r in rows}


def count_completed_analyses_for_ticker(ticker: str) -> int:
    """Accessions for ticker that already have a sentiment analysis row."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM filings f
            JOIN analyses a ON a.accession = f.accession
            WHERE f.ticker = ?
            """,
            (ticker.upper(),),
        ).fetchone()
        return int(row["n"]) if row else 0


def analysis_complete(accession: str) -> bool:
    return get_analysis(accession) is not None

