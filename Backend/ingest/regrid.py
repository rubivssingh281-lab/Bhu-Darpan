"""Regrid heterogeneous source grids onto the common analysis grid.

Bilinear interpolation via xarray onto a regular lat/lon grid at COMMON_RES over the
requested region, so rainfall (0.25°), temperature (1.0°) and satellite fields all
share one grid and can be fused/compared cell-by-cell.
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from .config import REGIONS, res_for


def target_grid(region: str, res: float | None = None):
    res = res or res_for(region)
    lat0, lat1, lon0, lon1 = REGIONS[region]
    lats = np.round(np.arange(lat0, lat1 + 1e-6, res), 4)
    lons = np.round(np.arange(lon0, lon1 + 1e-6, res), 4)
    return lats, lons


def regrid(ds: xr.Dataset, region: str, res: float | None = None) -> xr.Dataset:
    res = res or res_for(region)
    lats, lons = target_grid(region, res)
    # ensure ascending coords for interp
    if ds.lat[0] > ds.lat[-1]:
        ds = ds.sortby("lat")
    if ds.lon[0] > ds.lon[-1]:
        ds = ds.sortby("lon")
    out = ds.interp(lat=lats, lon=lons, method="linear")
    out.attrs.update(regridded_to=f"{res}deg regular grid", region=region)
    return out
