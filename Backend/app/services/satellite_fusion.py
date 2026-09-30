"""Fuse satellite surface temperature (LST) into the climate state.

Connects the satellite side to the digital twin: a satellite land-surface-temperature
field is assimilated into the gridded 2 m air-temperature analysis via the same
Cressman successive-correction routine used for multi-source fusion. This yields a
satellite-corrected surface-temperature state and quantifies how much the satellite
observations adjusted the twin.

LST source priority:
  1. INSAT 3RIMG_L2B_LST granule (MOSDAC) — set MOSDAC_LST_GRANULE to a local file;
     decoded via ingest.sources.mosdac.read_local().
  2. NASA POWER `TS` (Earth skin temperature) — open, credential-free stand-in,
     ingested as the `lst` gridded variable.
"""
from __future__ import annotations

import os

import numpy as np

from . import gridded_analysis as ga


def _downsample(lats, lons, grid, step_lat, step_lon):
    return {
        "lats": [round(float(x), 3) for x in lats[::step_lat]],
        "lons": [round(float(x), 3) for x in lons[::step_lon]],
        "grid": [[None if not np.isfinite(v) else round(float(v), 2) for v in row[::step_lon]]
                 for row in grid[::step_lat]],
    }


def fuse_surface_temperature(region: str = "jk") -> dict | None:
    """Assimilate the satellite LST field into the air-temperature (tmean) analysis.

    Returns the before/after surface-temperature grids, the per-cell adjustment the
    satellite made, and district samples — or None if either field is unavailable.
    """
    air = ga.anomaly("tmean", region)
    lst = ga.anomaly("lst", region)
    if air is None or lst is None:
        return None

    lats = np.asarray(air["lats"], float)
    lons = np.asarray(air["lons"], float)
    air_val = np.asarray(air["value"], float)
    lst_val = np.asarray(lst["value"], float)

    # Grids share the region/resolution; if the LST grid differs, sample it onto the
    # air-temp grid nearest-neighbour so observations align.
    if lst_val.shape != air_val.shape:
        li = np.asarray(lst["lats"], float); lo = np.asarray(lst["lons"], float)
        resampled = np.full_like(air_val, np.nan)
        for i, la in enumerate(lats):
            ii = int(np.abs(li - la).argmin())
            for j, ln in enumerate(lons):
                jj = int(np.abs(lo - ln).argmin())
                resampled[i, j] = lst_val[ii, jj]
        lst_val = resampled

    # Build satellite observations (lat, lon, LST) from every finite cell and
    # assimilate them into the air-temperature field (Cressman).
    obs = [(float(lats[i]), float(lons[j]), float(lst_val[i, j]))
           for i in range(len(lats)) for j in range(len(lons))
           if np.isfinite(lst_val[i, j])]
    fused = ga.assimilate(air_val, lats, lons, obs, radius_deg=0.6, alpha=0.5)

    adj = fused - air_val
    fin = adj[np.isfinite(adj)]
    source = ("INSAT 3RIMG_L2B_LST (MOSDAC)" if os.getenv("MOSDAC_LST_GRANULE")
              else "NASA POWER TS (satellite skin temperature)")

    step_lat = max(1, len(lats) // 24)
    step_lon = max(1, len(lons) // 24)

    districts = []
    for name, la, ln in ga.markers_for(region):
        i = int(np.abs(lats - la).argmin())
        j = int(np.abs(lons - ln).argmin())
        if np.isfinite(fused[i, j]):
            districts.append({
                "name": name,
                "air_temp": round(float(air_val[i, j]), 2),
                "satellite_lst": round(float(lst_val[i, j]), 2) if np.isfinite(lst_val[i, j]) else None,
                "fused": round(float(fused[i, j]), 2),
                "adjustment": round(float(adj[i, j]), 2),
            })

    return {
        "region": region,
        "variable": "surface_temperature",
        "units": "degC",
        "method": "Cressman successive-correction assimilation of satellite LST into 2 m air-temperature analysis",
        "lst_source": source,
        "air_source": air["source"],
        "period": air["period"],
        "n_satellite_obs": len(obs),
        "mean_abs_adjustment_c": round(float(np.nanmean(np.abs(fin))), 3) if fin.size else 0.0,
        "max_abs_adjustment_c": round(float(np.nanmax(np.abs(fin))), 3) if fin.size else 0.0,
        "air": _downsample(lats, lons, air_val, step_lat, step_lon),
        "fused": _downsample(lats, lons, fused, step_lat, step_lon),
        "districts": districts,
    }
