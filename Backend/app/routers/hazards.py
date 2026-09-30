"""Public climate-hazard analytics (drought / heatwave / monsoon)."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import hazards

router = APIRouter(prefix="/api/hazards", tags=["hazards"])


@router.get("")
def all_hazards():
    return hazards.summary()


@router.get("/drought")
def drought():
    return hazards.drought()


@router.get("/heatwave")
def heatwave():
    return hazards.heatwave()


@router.get("/monsoon")
def monsoon():
    return hazards.monsoon()


@router.get("/analytics")
def analytics():
    return hazards.analytics()
