"""Public climate digital-twin API (Jammu & Kashmir pilot).

No authentication — serves aggregate, non-sensitive climate intelligence derived
from 50 years of real J&K daily data.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services import climate

router = APIRouter(prefix="/api/climate", tags=["climate"])


@router.get("/current")
def current():
    return climate.current_state()


@router.get("/forecast")
def forecast(var: str = Query("rainfall", pattern="^(rainfall|temperature|soil|drought)$")):
    if var in ("soil", "drought"):
        return climate.derived_forecast(var)
    return climate.forecast(var)


@router.get("/districts")
def districts(layer: str = Query("rain", pattern="^(rain|temp|soil)$")):
    return climate.districts(layer)


@router.post("/whatif")
def whatif(body: dict):
    try:
        rain = float(body.get("rain_pct", 0))
        temp = float(body.get("temp_c", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "rain_pct and temp_c must be numbers")
    return climate.whatif(rain, temp)


@router.get("/data")
def data():
    return climate.data_summary()


@router.get("/insights")
def insights():
    return climate.insights()
