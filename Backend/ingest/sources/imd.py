"""IMD Pune gridded source (production ground-truth) via `imdlib`.

Downloads IMD gridded rainfall (0.25°) and temperature (1.0°) binary `.grd` files
from the IMD Pune server and decodes them to xarray. This is the intended national
ground source; it requires the IMD Pune server (imdpune.gov.in) to be reachable —
that server is frequently unavailable, in which case `fetch()` raises a clear error
and the pipeline can fall back to another source.
"""
from __future__ import annotations

from datetime import datetime

import xarray as xr

from ..config import GRIDDED_DIR, REGIONS, VARIABLES

_CACHE = GRIDDED_DIR / "_imd_raw"


def _years(start: str, end: str) -> tuple[int, int]:
    return datetime.strptime(start, "%Y%m%d").year, datetime.strptime(end, "%Y%m%d").year


def _one(var_type: str, y0: int, y1: int) -> xr.Dataset:
    import imdlib as imd  # imported lazily; heavy dependency

    _CACHE.mkdir(parents=True, exist_ok=True)
    try:
        obj = imd.get_data(var_type, y0, y1, fn_format="yearwise", file_dir=str(_CACHE))
    except Exception as exc:  # network / server failure
        raise RuntimeError(
            f"IMD Pune server unreachable while downloading {var_type} "
            f"({y0}-{y1}). Retry when imdpune.gov.in is available. Detail: {exc}"
        ) from exc
    return obj.get_xarray()


def fetch(var: str, region: str, start: str, end: str) -> xr.Dataset:
    y0, y1 = _years(start, end)
    lat0, lat1, lon0, lon1 = REGIONS[region]

    if var == "tmean":
        tmax = _one("tmax", y0, y1)["tmax"]
        tmin = _one("tmin", y0, y1)["tmin"]
        da = ((tmax + tmin) / 2.0).rename("tmean")
    else:
        var_type = VARIABLES[var]["imd"]
        da = _one(var_type, y0, y1)[var_type].rename(var)

    da = da.sel(time=slice(start[:4] + "-" + start[4:6] + "-" + start[6:],
                           end[:4] + "-" + end[4:6] + "-" + end[6:]))
    da = da.where(da > -900)  # IMD missing value
    da = da.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))

    out = da.to_dataset(name=var)
    out[var].attrs.update(units=VARIABLES[var]["units"],
                          long_name=VARIABLES[var]["long_name"], source="IMD Pune")
    out.attrs.update(source="IMD Pune (imdlib)")
    return out
