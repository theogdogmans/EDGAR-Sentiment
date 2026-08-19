from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .edgar.client import search_companies
from .pipeline import analyze_filing, company_overview, filing_detail
from .preload import ensure_started, start as start_preload, status as preload_status
from .sp500 import refresh_sp500


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    ensure_started()
    yield


app = FastAPI(title="edgar-sentiment", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/search")
def search(q: str = Query("", min_length=0)) -> dict:
    return {"results": search_companies(q, limit=20)}


@app.get("/api/sp500")
def sp500() -> dict:
    if db.sp500_count() < 400:
        refresh_sp500()
    companies = []
    for row in db.list_sp500():
        item = dict(row)
        item["ready"] = int(item.get("analyzed") or 0) >= 3
        companies.append(item)
    return {"companies": companies, "preload": preload_status()}


@app.get("/api/preload")
def preload_get() -> dict:
    return preload_status()


@app.post("/api/preload")
def preload_post() -> dict:
    return start_preload(background=True)


@app.get("/api/company/{ticker}")
def company(ticker: str, refresh: bool = False) -> dict:
    try:
        return company_overview(ticker, refresh=refresh)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SEC request failed: {exc}") from exc


@app.post("/api/filings/{accession}/analyze")
def analyze(accession: str, force: bool = False) -> dict:
    try:
        return analyze_filing(accession, force=force)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Analysis failed: {exc}") from exc


@app.get("/api/filings/{accession}")
def filing(accession: str) -> dict:
    try:
        return filing_detail(accession)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
