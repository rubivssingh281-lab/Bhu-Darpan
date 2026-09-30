"""Near-real-time data-refresh API (public).

Lets the dashboard pull the latest available reanalysis window on demand and shows
when the twin was last refreshed — the "continuously evolving" part of the digital
twin. Heavy work runs in a threadpool so the event loop stays responsive.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool

from ..services import refresh

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.get("/status")
def ingest_status() -> dict:
    return refresh.status()


@router.post("/refresh")
async def ingest_refresh(region: str | None = Query(None)) -> dict:
    """Fetch the latest available window for every live layer (or only `region`)."""
    return await run_in_threadpool(refresh.refresh_now, region)
