"""Public API over the ingested gridded NetCDF datasets (real IMD/POWER/INSAT grids)."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from ingest.config import GRIDDED_DIR, MANIFEST  # top-level package (Backend on sys.path)

router = APIRouter(prefix="/api/gridded", tags=["gridded"])


def _manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"datasets": []}


@router.get("/status")
def status():
    m = _manifest()
    ds = sorted(m.get("datasets", []), key=lambda d: d.get("created_at", ""), reverse=True)
    return {
        "count": len(ds),
        "datasets": ds,
        "sources": {
            "power": "NASA POWER regional daily grid — open, live",
            "imd": "IMD Pune gridded (imdlib) — public; server must be reachable",
            "mosdac": "INSAT L2B (LST/SST/rainfall) — needs a MOSDAC account",
        },
    }


@lru_cache(maxsize=16)
def _field(ds_id: str, max_cells: int = 28):
    import xarray as xr

    path = GRIDDED_DIR / f"{ds_id}.nc"
    if not path.exists():
        return None
    ds = xr.open_dataset(path)
    var = [v for v in ds.data_vars][0]
    da = ds[var]
    if "time" in da.dims:
        da = da.mean("time", skipna=True)
    # thin to <= max_cells per axis for a light payload
    ny, nx = da.sizes["lat"], da.sizes["lon"]
    sy, sx = max(1, ny // max_cells), max(1, nx // max_cells)
    da = da.isel(lat=slice(None, None, sy), lon=slice(None, None, sx))
    vals = np.asarray(da.values, dtype=float)
    finite = vals[np.isfinite(vals)]
    grid = [[None if not np.isfinite(v) else round(float(v), 2) for v in row] for row in vals]
    return {
        "var": var,
        "lats": [round(float(x), 3) for x in np.asarray(da.lat.values)],
        "lons": [round(float(x), 3) for x in np.asarray(da.lon.values)],
        "values": grid,
        "vmin": round(float(finite.min()), 2) if finite.size else None,
        "vmax": round(float(finite.max()), 2) if finite.size else None,
        "mean": round(float(finite.mean()), 2) if finite.size else None,
    }


@router.get("/field")
def field(id: str = Query(...)):
    f = _field(id)
    if f is None:
        raise HTTPException(404, f"gridded dataset {id!r} not found")
    meta = next((d for d in _manifest()["datasets"] if d["id"] == id), {})
    return {**f, "id": id, "units": meta.get("units"), "bbox": meta.get("bbox"),
            "source": meta.get("source"), "res_deg": meta.get("res_deg")}


def _grid2list(arr):
    return [[None if not np.isfinite(v) else round(float(v), 2) for v in row] for row in arr]


@router.get("/vars")
def vars(region: str = "jk"):
    from ..services import gridded_analysis as ga
    return {"region": region, "vars": ga.available(region)}


@router.get("/anomaly")
def anomaly(var: str = Query("tmean"), region: str = "jk"):
    from ..services import gridded_analysis as ga
    a = ga.anomaly(var, region)
    if a is None:
        raise HTTPException(404, f"no ingested grid for {var!r} over {region!r}. "
                                 f"Run: python -m ingest.pipeline --var {var} --region {region} …")
    d = ga.districts(var, region)
    return {
        "var": a["var"], "units": a["units"], "period": a["period"], "source": a["source"],
        "res_deg": a["res_deg"], "bbox": list(_manifest_bbox(region)),
        "lats": [round(float(x), 3) for x in a["lats"]],
        "lons": [round(float(x), 3) for x in a["lons"]],
        "anomaly": _grid2list(a["anomaly"]),
        "value": _grid2list(a["value"]),
        "amin": round(a["amin"], 2), "amax": round(a["amax"], 2), "amean": round(a["amean"], 2),
        "n_cells": a["n_cells"], "valid_cells": a["valid_cells"],
        "districts": d["districts"] if d else [],
    }


@router.get("/forecast")
def gridded_forecast(var: str = Query("tmean"), region: str = "jk",
                     lead: int = Query(7, ge=1, le=14)):
    from ..services import grid_ml_forecast as gml, gridded_analysis as ga
    f = gml.forecast_field(var, region, lead)      # ML forecaster (gated)
    if f is None:
        f = ga.forecast_field(var, region, lead)   # fallback: persistence + climatology
    if f is None:
        raise HTTPException(404, f"no ingested grid for {var!r} over {region!r}")
    m = gml.metrics(var, region)
    lead_skill = (m["leads"].get(str(lead)) if m else None)
    return {
        "var": f["var"], "units": f["units"], "lead": lead, "target_date": f["target_date"],
        "source": f["source"], "res_deg": f["res_deg"], "bbox": list(_manifest_bbox(region)),
        "method": f.get("method"),
        "lats": [round(float(x), 3) for x in f["lats"]],
        "lons": [round(float(x), 3) for x in f["lons"]],
        "anomaly": _grid2list(f["anomaly"]), "value": _grid2list(f["value"]),
        "amin": round(f["amin"], 2), "amax": round(f["amax"], 2),
        "districts": f["districts"], "skill": lead_skill,
    }


@router.get("/forecast/skill")
def gridded_forecast_skill(var: str = Query("tmean"), region: str = "jk"):
    """Per-lead ML validation vs climatology AND persistence baselines."""
    from ..services import grid_ml_forecast as gml, gridded_analysis as ga
    m = gml.metrics(var, region)
    if m is None:
        sk = ga.forecast_skill(var, region)
        if sk is None:
            raise HTTPException(404, "no multi-year record ingested for validation")
        return sk
    return m


def _manifest_bbox(region: str):
    from ingest.config import REGIONS
    return REGIONS.get(region, (0, 0, 0, 0))
