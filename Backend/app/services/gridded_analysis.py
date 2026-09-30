"""Per-cell gridded analysis — the modelling substrate built on the ingested grids.

Turns the ingested daily NetCDF fields + per-cell climatology into:
  * a per-cell anomaly field (value − climatology) for the region,
  * district values sampled straight from the real grid, and
  * a Cressman successive-correction `assimilate()` utility that fuses point/second
    -source observations into the grid (activated automatically when a second gridded
    source is available for the same period).

Everything here reads the real NetCDF produced by `ingest/` — no synthetic state.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache

import numpy as np

from ingest.config import GRIDDED_DIR, MANIFEST

# Real district coordinates (lat, lon) for grid sampling
DISTRICTS_LL = [
    ("Baramulla", 34.20, 74.35), ("Srinagar", 34.08, 74.80),
    ("Kishtwar", 33.31, 75.77), ("Doda", 33.15, 75.55),
    ("Anantnag", 33.73, 75.15), ("Udhampur", 32.93, 75.13),
    ("Rajouri", 33.38, 74.31), ("Kathua", 32.37, 75.52), ("Jammu", 32.73, 74.87),
]

# Major-city markers for the national view
INDIA_CITIES = [
    ("Delhi", 28.61, 77.21), ("Mumbai", 19.08, 72.88), ("Kolkata", 22.57, 88.36),
    ("Chennai", 13.08, 80.27), ("Bengaluru", 12.97, 77.59), ("Hyderabad", 17.38, 78.49),
    ("Ahmedabad", 23.03, 72.58), ("Srinagar", 34.08, 74.80), ("Jaipur", 26.91, 75.79),
    ("Lucknow", 26.85, 80.95), ("Bhopal", 23.26, 77.41), ("Guwahati", 26.14, 91.74),
    ("Nagpur", 21.15, 79.09), ("Patna", 25.59, 85.14), ("Bhubaneswar", 20.30, 85.82),
]


def markers_for(region: str):
    return INDIA_CITIES if region == "india" else DISTRICTS_LL


def _manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"datasets": []}


def _find(var: str, region: str, climatology: bool,
          max_days: int | None = None, min_days: int | None = None,
          source_contains: str | None = None):
    best = None
    for d in _manifest()["datasets"]:
        if d["var"] != var or d["region"] != region:
            continue
        is_clim = d.get("kind") == "climatology"
        if is_clim != climatology:
            continue
        if source_contains and source_contains.lower() not in d.get("source", "").lower():
            continue
        if not is_clim:
            days = d.get("days", 0)
            if max_days is not None and days > max_days:
                continue
            if min_days is not None and days < min_days:
                continue
        if best is None or d.get("created_at", "") > best.get("created_at", ""):
            best = d
    return best


def available(region: str = "jk") -> list[str]:
    """Variables that have both a daily field and a climatology for this region."""
    out = []
    for var in ("rain", "tmean", "tmax", "tmin", "lst"):
        if _find(var, region, False) and _find(var, region, True):
            out.append(var)
    return out


def assimilate(grid: np.ndarray, lats, lons, obs: list[tuple], radius_deg=1.0, alpha=0.6):
    """Cressman successive-correction: nudge `grid` toward point observations `obs`
    = [(lat, lon, value)], within `radius_deg`. Returns a fused copy. With no obs it
    returns the grid unchanged (single-source passthrough)."""
    if not obs:
        return grid
    g = grid.copy()
    LA, LO = np.meshgrid(lats, lons, indexing="ij")
    for (olat, olon, oval) in obs:
        if not np.isfinite(oval):
            continue
        dist2 = (LA - olat) ** 2 + (LO - olon) ** 2
        w = np.clip((radius_deg ** 2 - dist2) / (radius_deg ** 2 + dist2), 0, None)
        # nearest current grid value to the obs to form the increment
        gi = np.unravel_index(np.nanargmin(dist2), dist2.shape)
        incr = oval - g[gi]
        g = g + alpha * w * incr
    return g


@lru_cache(maxsize=8)
def anomaly(var: str, region: str = "jk") -> dict | None:
    import xarray as xr

    # Analysis uses the POWER recent snapshot window (<= ~180 days), not the multi-year
    # record and not the secondary Open-Meteo source (kept for fusion).
    daily_m = (_find(var, region, False, max_days=180, source_contains="POWER")
               or _find(var, region, False, max_days=180) or _find(var, region, False))
    clim_m = _find(var, region, True)
    if not daily_m or not clim_m:
        return None

    da = xr.open_dataset(GRIDDED_DIR / f"{daily_m['id']}.nc")[var]
    clim = xr.open_dataset(GRIDDED_DIR / f"{clim_m['id']}.nc")[var]

    # months present in the daily window
    months = sorted(set(int(m) for m in np.atleast_1d(da["time"].dt.month.values)))
    clim_sel = clim.isel(month=[m - 1 for m in months]).mean("month")

    value = da.mean("time", skipna=True)
    lats = np.asarray(value.lat.values, dtype=float)
    lons = np.asarray(value.lon.values, dtype=float)
    val = np.asarray(value.values, dtype=float)
    anom = val - np.asarray(clim_sel.values, dtype=float)

    # For rainfall express anomaly as % of the climatological normal too
    pct = None
    if var == "rain":
        with np.errstate(divide="ignore", invalid="ignore"):
            pct = np.where(np.asarray(clim_sel.values) > 0.1,
                           anom / np.asarray(clim_sel.values) * 100.0, np.nan)

    fin = anom[np.isfinite(anom)]
    return {
        "var": var, "region": region, "units": daily_m["units"],
        "period": f"{daily_m['start']}–{daily_m['end']}",
        "source": daily_m["source"], "res_deg": daily_m["res_deg"],
        "lats": lats, "lons": lons,
        "value": val, "anomaly": anom, "anomaly_pct": pct,
        "amin": float(np.nanmin(fin)) if fin.size else None,
        "amax": float(np.nanmax(fin)) if fin.size else None,
        "amean": float(np.nanmean(fin)) if fin.size else None,
        "n_cells": int(val.size), "valid_cells": int(np.isfinite(val).sum()),
    }


def _sample(lats, lons, grid, lat, lon):
    i = int(np.abs(lats - lat).argmin())
    j = int(np.abs(lons - lon).argmin())
    v = grid[i, j]
    return None if not np.isfinite(v) else float(v)


def districts(var: str, region: str = "jk") -> dict | None:
    a = anomaly(var, region)
    if a is None:
        return None
    out = []
    for name, lat, lon in markers_for(region):
        out.append({
            "name": name, "lat": lat, "lon": lon,
            "value": round(_sample(a["lats"], a["lons"], a["value"], lat, lon) or 0, 2),
            "anomaly": round(_sample(a["lats"], a["lons"], a["anomaly"], lat, lon) or 0, 2),
        })
    return {"var": var, "region": region, "units": a["units"], "districts": out}


# --------------------------------------------------------------------------- #
# Per-cell gridded forecast (persistence of the current anomaly + climatology),
# validated on the multi-year record.
# --------------------------------------------------------------------------- #
def _decay(lead: int) -> float:
    # Daily-weather persistence decays fast; by ~1 week the best estimate is the
    # climatology, so the anomaly relaxes toward zero over the horizon.
    return 0.6 ** lead


@lru_cache(maxsize=32)
def forecast_field(var: str, region: str = "jk", lead: int = 7) -> dict | None:
    """Forecast the per-cell field `lead` days past the analysis snapshot:
    forecast_anomaly = current_anomaly · decay(lead); value = climatology(target month)
    + forecast_anomaly."""
    import xarray as xr

    a = anomaly(var, region)
    clim_m = _find(var, region, True)
    if a is None or not clim_m:
        return None
    clim = xr.open_dataset(GRIDDED_DIR / f"{clim_m['id']}.nc")[var]

    end = a["period"].split("–")[-1]              # YYYYMMDD (snapshot end)
    target = datetime.strptime(end, "%Y%m%d") + timedelta(days=lead)
    clim_t = np.asarray(clim.isel(month=target.month - 1).values, dtype=float)

    fc_anom = a["anomaly"] * _decay(lead)
    fc_value = clim_t + fc_anom
    fin = fc_anom[np.isfinite(fc_anom)]

    districts = []
    for name, lat, lon in markers_for(region):
        districts.append({
            "name": name, "lat": lat, "lon": lon,
            "value": round(_sample(a["lats"], a["lons"], fc_value, lat, lon) or 0, 2),
            "anomaly": round(_sample(a["lats"], a["lons"], fc_anom, lat, lon) or 0, 2),
        })
    return {
        "var": var, "region": region, "units": a["units"], "lead": lead,
        "target_date": target.strftime("%Y-%m-%d"), "res_deg": a["res_deg"],
        "method": "Persistence + climatology", "source": a["source"],
        "lats": a["lats"], "lons": a["lons"],
        "value": fc_value, "anomaly": fc_anom,
        "amin": float(np.nanmin(fin)) if fin.size else None,
        "amax": float(np.nanmax(fin)) if fin.size else None,
        "districts": districts,
    }


@lru_cache(maxsize=8)
def forecast_skill(var: str, region: str = "jk") -> dict | None:
    """Backtest the persistence+climatology forecast on the multi-year record,
    per cell, over the last 365 days — reports RMSE and skill vs climatology by lead."""
    import xarray as xr

    rec = _find(var, region, False, min_days=200)
    clim_m = _find(var, region, True)
    if not rec or not clim_m:
        return None
    da = xr.open_dataset(GRIDDED_DIR / f"{rec['id']}.nc")[var]
    clim = xr.open_dataset(GRIDDED_DIR / f"{clim_m['id']}.nc")[var]

    obs = np.asarray(da.values, dtype=float)                       # (T, ny, nx)
    months = np.atleast_1d(da["time"].dt.month.values).astype(int)
    clim_arr = np.asarray(clim.values, dtype=float)                # (13, ny, nx)
    clim_daily = clim_arr[months - 1]                              # (T, ny, nx)
    anom = obs - clim_daily
    T = obs.shape[0]
    test = slice(max(0, T - 365), T)

    def rmse(a, b):
        e = (a - b)[test]
        e = e[np.isfinite(e)]
        return float(np.sqrt(np.mean(e ** 2))) if e.size else float("nan")

    base = rmse(obs, clim_daily)
    leads = {}
    for L in (1, 7, 14):
        pred = np.full_like(obs, np.nan)
        pred[L:] = clim_daily[L:] + anom[:-L] * _decay(L)
        r = rmse(obs, pred)
        leads[str(L)] = {
            "rmse": round(r, 2),
            "skill_pct": round((1 - r / base) * 100, 1) if base else None,
        }
    return {"var": var, "clim_rmse": round(base, 2), "units": rec["units"],
            "test_days": min(365, T), "leads": leads,
            "method": "Persistence of per-cell anomaly + climatology"}
