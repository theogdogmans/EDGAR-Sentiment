from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime, timezone
from typing import Any

from . import db
from .config import MAX_FILINGS
from .edgar.client import list_recent_filings, load_company_facts, resolve_ticker
from .pipeline import analyze_filing
from .sp500 import refresh_sp500, sp500_tickers

_lock = threading.Lock()
_thread: threading.Thread | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status() -> dict[str, Any]:
    raw = db.meta_get("preload")
    if raw:
        data = json.loads(raw)
    else:
        data = {
            "running": False,
            "stage": "idle",
            "current": None,
            "message": "Not started",
            "errors": [],
            "started_at": None,
            "finished_at": None,
        }
    data["coverage"] = db.coverage()
    return data


def _save(payload: dict[str, Any]) -> None:
    keep = {k: v for k, v in payload.items() if k != "coverage"}
    db.meta_set("preload", json.dumps(keep), _now())
    try:
        from .supabase_sync import set_preload_status

        set_preload_status({**keep, "coverage": db.coverage()})
    except Exception:
        pass


def status() -> dict[str, Any]:
    return _status()


def _run() -> None:
    state = _status()
    state.update(
        {
            "running": True,
            "stage": "constituents",
            "message": "Loading S&P 500 list",
            "current": None,
            "errors": state.get("errors") or [],
            "started_at": state.get("started_at") or _now(),
            "finished_at": None,
        }
    )
    _save(state)
    try:
        refresh_sp500()
        tickers = sp500_tickers()
        state["stage"] = "filings"
        for i, ticker in enumerate(tickers, start=1):
            state["current"] = ticker
            state["message"] = f"Fetching filings {i}/{len(tickers)} {ticker}"
            _save(state)
            try:
                company = resolve_ticker(ticker)
                filings = list_recent_filings(ticker, MAX_FILINGS, force=False)
                if not filings:
                    filings = list_recent_filings(ticker, MAX_FILINGS, force=True)
                load_company_facts(company["cik"])
            except Exception as exc:  # noqa: BLE001
                state["errors"].append({"ticker": ticker, "error": str(exc)})
                state["errors"] = state["errors"][-25:]
                continue

        state["stage"] = "sentiment"
        for i, ticker in enumerate(tickers, start=1):
            state["current"] = ticker
            try:
                filings = list_recent_filings(ticker, MAX_FILINGS, force=False)
                for filing in filings:
                    if db.get_analysis(filing["accession"]):
                        continue
                    state["message"] = f"Scoring {ticker} {filing['form']} {filing['filed']} ({i}/{len(tickers)})"
                    _save(state)
                    try:
                        analyze_filing(filing["accession"])
                    except Exception as exc:  # noqa: BLE001
                        state["errors"].append(
                            {"ticker": ticker, "accession": filing["accession"], "error": str(exc)}
                        )
                        state["errors"] = state["errors"][-25:]
            except Exception as exc:  # noqa: BLE001
                state["errors"].append({"ticker": ticker, "error": str(exc)})
                state["errors"] = state["errors"][-25:]

        state.update(
            {
                "running": False,
                "stage": "done",
                "current": None,
                "message": "S&P 500 preload complete",
                "finished_at": _now(),
            }
        )
        _save(state)
    except Exception as exc:  # noqa: BLE001
        state.update(
            {
                "running": False,
                "stage": "error",
                "message": f"Preload failed: {exc}",
                "finished_at": _now(),
            }
        )
        state["errors"].append({"error": str(exc), "trace": traceback.format_exc()[-1500:]})
        _save(state)


def start(background: bool = True) -> dict[str, Any]:
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return _status()
        if background:
            _thread = threading.Thread(target=_run, name="sp500-preload", daemon=True)
            _thread.start()
        else:
            _run()
    return _status()


def ensure_started() -> None:
    cov = db.coverage()
    if cov["companies"] >= 400 and cov["ready"] >= cov["companies"]:
        return
    start(background=True)
