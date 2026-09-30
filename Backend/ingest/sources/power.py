"""NASA POWER source — open, credential-free gridded daily reanalysis.

Regional daily grid at 0.5°. One parameter per request (API constraint), returned
as NetCDF and opened with xarray. Used as the live, runnable ground/reanalysis
source to demonstrate the full ingestion pipeline.

https://power.larc.nasa.gov/docs/services/api/temporal/daily/
"""
from __future__ import annotations

import math
import tempfile

import numpy as np
import requests
import xarray as xr

from ..config import REGIONS, VARIABLES

_BASE = "https://power.larc.nasa.gov/api/temporal/daily/regional"
_CLIM = "https://power.larc.nasa.gov/api/temporal/climatology/regional"
_MAX_TILE = 8.0   # POWER regional caps each dimension at ~10°; tile below that


def _edges(a: float, b: float, step: float) -> list[float]:
    # Even split into n tiles each <= step and (since regions are large) >= 2° — POWER
    # requires each regional dimension to be between 2° and 10°.
    n = max(1, math.ceil((b - a) / step))
    size = (b - a) / n
    return [round(a + size * i, 4) for i in range(n + 1)]


def _tiles(lat0, lat1, lon0, lon1):
    la, lo = _edges(lat0, lat1, _MAX_TILE), _edges(lon0, lon1, _MAX_TILE)
    for i in range(len(la) - 1):
        for j in range(len(lo) - 1):
            yield la[i], la[i + 1], lo[j], lo[j + 1]


def _fetch_grid(base: str, param: str, bbox, extra: dict) -> xr.DataArray:
    """Fetch a (possibly tiled) regional grid and mosaic tiles by coordinates."""
    lat0, lat1, lon0, lon1 = bbox
    das = []
    for (a0, a1, o0, o1) in _tiles(lat0, lat1, lon0, lon1):
        params = {"parameters": param, "community": "AG",
                  "latitude-min": a0, "latitude-max": a1,
                  "longitude-min": o0, "longitude-max": o1, "format": "NETCDF", **extra}
        r = requests.get(base, params=params, timeout=180)
        r.raise_for_status()
        ds = _open_netcdf_bytes(r.content)
        dvar = param if param in ds.data_vars else list(ds.data_vars)[0]
        das.append(ds[dvar].where(ds[dvar] > -900))
    if len(das) == 1:
        return das[0]
    merged = xr.combine_by_coords(das, combine_attrs="drop")
    da = merged if isinstance(merged, xr.DataArray) else merged[list(merged.data_vars)[0]]
    # drop duplicate boundary rows/cols shared between tiles
    da = da.sortby("lat").sortby("lon")
    da = da.isel(lat=np.unique(da.lat, return_index=True)[1],
                 lon=np.unique(da.lon, return_index=True)[1])
    return da


def _open_netcdf_bytes(content: bytes) -> xr.Dataset:
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tf:
        tf.write(content)
        path = tf.name
    ds = xr.open_dataset(path)
    rename = {}
    for cand in ("latitude", "Latitude", "y"):
        if cand in ds.coords:
            rename[cand] = "lat"
    for cand in ("longitude", "Longitude", "x"):
        if cand in ds.coords:
            rename[cand] = "lon"
    return ds.rename(rename) if rename else ds


def fetch(var: str, region: str, start: str, end: str) -> xr.Dataset:
    """Fetch one canonical variable over a region for a YYYYMMDD date range.

    Returns an xarray Dataset with a single data variable named `var` and
    dimensions (time, lat, lon).
    """
    if var not in VARIABLES:
        raise ValueError(f"unknown variable {var!r}")
    if region not in REGIONS:
        raise ValueError(f"unknown region {region!r}")
    param = VARIABLES[var]["power"]
    bbox = REGIONS[region]

    # POWER daily/regional caps at ~1 year per request — chunk by calendar year
    # (and tile large regions spatially inside _fetch_grid).
    y0, y1 = int(start[:4]), int(end[:4])
    pieces = []
    for yr in range(y0, y1 + 1):
        s = start if yr == y0 else f"{yr}0101"
        e = end if yr == y1 else f"{yr}1231"
        pieces.append(_fetch_grid(_BASE, param, bbox, {"start": s, "end": e}))

    da = xr.concat(pieces, dim="time") if len(pieces) > 1 else pieces[0]
    out = da.to_dataset(name=var)
    out[var].attrs.update(units=VARIABLES[var]["units"],
                          long_name=VARIABLES[var]["long_name"], source="NASA POWER")
    out.attrs.update(source="NASA POWER", api=_BASE, native_res_deg=0.5)
    return out


def fetch_climatology(var: str, region: str) -> xr.Dataset:
    """Per-cell long-term climatology (13 = 12 months + annual) for a variable."""
    param = VARIABLES[var]["power"]
    da = _fetch_grid(_CLIM, param, REGIONS[region], {})
    if "time" in da.dims:                 # 13 steps → month index 0..11 + annual(12)
        da = da.rename({"time": "month"})
    out = da.to_dataset(name=var)
    out[var].attrs.update(units=VARIABLES[var]["units"], long_name="climatology")
    out.attrs.update(source="NASA POWER", api=_CLIM, native_res_deg=0.5, kind="climatology")
    return out
