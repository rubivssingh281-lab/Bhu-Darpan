"""MOSDAC / INSAT source (credential-gated).

INSAT-3D/3DR L2B products — Land Surface Temperature (3RIMG_L2B_LST), Sea Surface
Temperature (3RIMG_L2B_SST) and rainfall (3RIMG_L2B_IMC) — are distributed by
MOSDAC (https://www.mosdac.gov.in/) and require a registered account.

`read_local()` decodes an already-downloaded INSAT HDF5/NetCDF granule to xarray and
works offline. `fetch()` performs the authenticated download and needs credentials in
the environment (MOSDAC_USER / MOSDAC_PASS); without them it raises an actionable
error rather than guessing. Create the account yourself at mosdac.gov.in — this tool
never creates accounts or handles passwords on your behalf.
"""
from __future__ import annotations

import os

import xarray as xr

from ..config import REGIONS, VARIABLES

PRODUCTS = {
    "lst": "3RIMG_L2B_LST",
    "sst": "3RIMG_L2B_SST",
    "rain": "3RIMG_L2B_IMC",
}
_PORTAL = "https://www.mosdac.gov.in/"


def read_local(path: str, var: str, hint_names: list[str] | None = None) -> xr.Dataset:
    """Decode a locally-downloaded INSAT HDF5/NetCDF granule into a standard Dataset."""
    ds = xr.open_dataset(path)  # netCDF4 engine reads HDF5-EOS granules
    names = hint_names or list(ds.data_vars)
    dvar = next((n for n in names if n in ds.data_vars), list(ds.data_vars)[0])
    da = ds[dvar]
    rename = {}
    for cand in ("latitude", "Latitude", "y"):
        if cand in ds.coords:
            rename[cand] = "lat"
    for cand in ("longitude", "Longitude", "x"):
        if cand in ds.coords:
            rename[cand] = "lon"
    da = da.rename(rename) if rename else da
    out = da.to_dataset(name=var)
    out.attrs.update(source=f"INSAT/MOSDAC ({os.path.basename(path)})")
    return out


def fetch(var: str, region: str, start: str, end: str) -> xr.Dataset:
    user, pw = os.getenv("MOSDAC_USER"), os.getenv("MOSDAC_PASS")
    if not user or not pw:
        raise RuntimeError(
            "MOSDAC ingestion requires an account. Set MOSDAC_USER and MOSDAC_PASS "
            "in the environment (register at https://www.mosdac.gov.in/). This tool "
            "does not create accounts or enter passwords for you. Once a granule is "
            "downloaded, use mosdac.read_local(path, var) to decode it."
        )
    # With credentials, the real flow is: authenticate to the MOSDAC portal, place a
    # data order for the product over [start,end], poll until ready, download the
    # HDF5 granule(s), then read_local() each. Left as an authenticated integration
    # step because the order workflow and product paths are account-specific.
    raise NotImplementedError(
        f"Authenticated MOSDAC order/download for {PRODUCTS.get(var, var)} over "
        f"{region} {start}-{end} is not wired in this environment. Portal: {_PORTAL}"
    )
