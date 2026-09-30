"""Live weather desk — real-time conditions and headlines for the J&K pilot region."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import weather_live, weather_news

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/live")
def live(region: str = "jk"):
    try:
        return weather_live.current(region)
    except Exception as exc:  # upstream (Open-Meteo) unreachable / rate-limited
        raise HTTPException(status_code=503, detail=f"Live weather unavailable: {exc}")


@router.get("/news")
def news(region: str = "jk"):
    try:
        return weather_news.headlines(region)
    except Exception as exc:  # upstream news API unreachable / rate-limited / bad key
        raise HTTPException(status_code=503, detail=f"News unavailable: {exc}")
