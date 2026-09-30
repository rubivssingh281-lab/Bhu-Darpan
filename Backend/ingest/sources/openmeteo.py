"""Open-Meteo source — a second, independent reanalysis (ERA5-based), free & keyless.

Used to demonstrate genuine multi-source data assimilation: NASA POWER (MERRA-2) and
Open-Meteo (ERA5) are independent reanalyses, so fusing them reduces error and yields an
uncertainty (spread) field. The grid is built by sampling the archive API at the target
grid's cell centres (bulk points, chunked).

https://open-meteo.com/en/docs/historical-weather-api
"""
from __future__ import annotations

import time

import numpy as np
import requests
import xarray as xr

from ..config import REGIONS, VARIABLES

_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
_BATCH = 60
_SAMPLE_DEG = 0.5   # coarse sampling to stay within Open-Meteo's free rate limits


def _get(params):
    """GET with backoff on 429/5xx (Open-Meteo free-tier rate limits)."""
    delay = 3
    for attempt in range(5):
        r = requests.get(_ARCHIVE, params=params, timeout=120)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(delay)
            delay *= 2
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def fetch(var: str, region: str, start: str, end: str) -> xr.Dataset:
    daily = VARIABLES[var]["openmeteo"]
    lat0, lat1, lon0, lon1 = REGIONS[region]
    lats = np.round(np.arange(lat0, lat1 + 1e-6, _SAMPLE_DEG), 4)
    lons = np.round(np.arange(lon0, lon1 + 1e-6, _SAMPLE_DEG), 4)
    ny, nx = len(lats), len(lons)
    pts = [(i, j, float(lats[i]), float(lons[j])) for i in range(ny) for j in range(nx)]
    sd = f"{start[:4]}-{start[4:6]}-{start[6:]}"
    ed = f"{end[:4]}-{end[4:6]}-{end[6:]}"

    arr = None
    times = None
    for b in range(0, len(pts), _BATCH):
        chunk = pts[b:b + _BATCH]
        if b > 0:
            time.sleep(1.5)
        params = {
            "latitude": ",".join(f"{p[2]:.4f}" for p in chunk),
            "longitude": ",".join(f"{p[3]:.4f}" for p in chunk),
            "start_date": sd, "end_date": ed, "daily": daily, "timezone": "UTC",
        }
        data = _get(params)
        locs = data if isinstance(data, list) else [data]
        if times is None:
            times = np.array(locs[0]["daily"]["time"], dtype="datetime64[D]")
            arr = np.full((len(times), ny, nx), np.nan, dtype=np.float32)
        for (i, j, _, _), loc in zip(chunk, locs):
            vals = loc["daily"][daily]
            arr[:, i, j] = np.array([np.nan if v is None else v for v in vals], dtype=np.float32)

    da = xr.DataArray(arr, dims=["time", "lat", "lon"],
                      coords={"time": times, "lat": lats, "lon": lons}, name=var)
    out = da.to_dataset(name=var)
    out[var].attrs.update(units=VARIABLES[var]["units"],
                          long_name=VARIABLES[var]["long_name"], source="Open-Meteo (ERA5)")
    out.attrs.update(source="Open-Meteo (ERA5)", api=_ARCHIVE, native_res_deg=0.25)
    return out
