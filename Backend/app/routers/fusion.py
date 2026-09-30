"""Public multi-source data-assimilation API."""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from ..services import fusion, satellite_fusion

router = APIRouter(prefix="/api/fusion", tags=["fusion"])


@router.get("/surface-temp")
def surface_temp(region: str = "jk"):
    """Satellite LST assimilated into the air-temperature state (satellite→twin fusion)."""
    res = satellite_fusion.fuse_surface_temperature(region)
    if res is None:
        raise HTTPException(404, "Need both a gridded air-temperature (tmean) analysis and a "
                                 "satellite LST layer for this region. Ingest 'lst' via the pipeline.")
    return res


def _g(arr):
    return [[None if not np.isfinite(v) else round(float(v), 2) for v in row] for row in arr]


@router.get("/status")
def status(region: str = "jk"):
    return {"region": region, "vars": fusion.available(region),
            "method": "Optimal interpolation (inverse-error-variance weighting)",
            "sources": ["NASA POWER (MERRA-2)", "Open-Meteo (ERA5)"]}


@router.get("/field")
def field(var: str = Query("rain"), region: str = "jk"):
    f = fusion.fuse(var, region)
    if f is None:
        raise HTTPException(404, f"need both POWER and Open-Meteo grids for {var!r}/{region!r}. "
                                 f"Run the ingest pipeline for both sources.")
    return {
        "var": f["var"], "units": f["units"], "region": region, "res_deg": f["res_deg"],
        "period": f["period"],
        "method": f.get("method_detail") or "Optimal interpolation (BLUE)",
        "sources": f["sources"], "fused_rmse": f["fused_rmse"],
        "reduction_vs_best_pct": f["reduction_vs_best_pct"], "validated_against": f["validated_against"],
        "calibrated": f.get("calibrated", False),
        "method_detail": f.get("method_detail"), "error_correlation": f.get("error_correlation"),
        "lats": [round(float(x), 3) for x in f["lats"]],
        "lons": [round(float(x), 3) for x in f["lons"]],
        "anomaly": _g(f["anomaly"]), "spread": _g(f["spread"]),
        "amin": round(f["amin"], 2), "amax": round(f["amax"], 2),
        "spread_mean": f["spread_mean"], "spread_max": f["spread_max"],
        "districts": f["districts"],
    }
