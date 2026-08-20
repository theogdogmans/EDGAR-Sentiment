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
