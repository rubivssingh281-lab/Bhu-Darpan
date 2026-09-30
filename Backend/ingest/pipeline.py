"""ETL orchestrator: download → decode → regrid → store NetCDF + manifest.

CLI:
    python -m ingest.pipeline --source power --var rain --region jk \
        --start 20230601 --end 20230630
"""
from __future__ import annotations

import argparse
import importlib
import json
from datetime import datetime, timezone

import numpy as np
import xarray as xr

from .config import GRIDDED_DIR, MANIFEST, REGIONS, VARIABLES, res_for
from .regrid import regrid

SOURCES = {"power": "ingest.sources.power", "imd": "ingest.sources.imd",
           "mosdac": "ingest.sources.mosdac", "openmeteo": "ingest.sources.openmeteo"}


def _load_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"datasets": []}


def _save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=2, default=str), encoding="utf-8")


def run(source: str, var: str, region: str, start: str, end: str) -> dict:
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r} (choices: {list(SOURCES)})")
    if var not in VARIABLES:
        raise ValueError(f"unknown var {var!r} (choices: {list(VARIABLES)})")
    if region not in REGIONS:
        raise ValueError(f"unknown region {region!r} (choices: {list(REGIONS)})")

    mod = importlib.import_module(SOURCES[source])
    print(f"[1/4] Downloading {var} from {source} · {region} · {start}-{end} …")
    raw = mod.fetch(var, region, start, end)

    print("[2/4] Regridding to common grid …")
    grid = regrid(raw, region)

    print("[3/4] Computing statistics …")
    field = grid[var]
    tmean = field.mean("time", skipna=True) if "time" in field.dims else field
    vals = np.asarray(tmean.values, dtype=float)
    valid = int(np.isfinite(vals).sum())
    nlat, nlon = vals.shape[-2], vals.shape[-1]

    ds_id = f"{source}_{var}_{region}_{start}_{end}"
    path = GRIDDED_DIR / f"{ds_id}.nc"
    print(f"[4/4] Writing {path.name} …")
    grid.to_netcdf(path)

    entry = {
        "id": ds_id, "source": raw.attrs.get("source", source), "var": var,
        "units": VARIABLES[var]["units"], "region": region, "bbox": REGIONS[region],
        "res_deg": res_for(region), "start": start, "end": end,
        "days": int(field.sizes.get("time", 1)),
        "grid_shape": [nlat, nlon], "n_cells": nlat * nlon, "valid_cells": valid,
        "mean": round(float(np.nanmean(vals)), 3),
        "min": round(float(np.nanmin(vals)), 3),
        "max": round(float(np.nanmax(vals)), 3),
        "native_res_deg": raw.attrs.get("native_res_deg"),
        "path": str(path.relative_to(GRIDDED_DIR.parent.parent)),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "ingested",
    }
    m = _load_manifest()
    m["datasets"] = [d for d in m["datasets"] if d["id"] != ds_id] + [entry]
    _save_manifest(m)
    print(f"✓ ingested {ds_id}: {nlat}×{nlon} grid, {entry['days']} days, "
          f"mean {entry['mean']} {entry['units']}")
    return entry


def run_climatology(source: str, var: str, region: str) -> dict:
    """Ingest a per-cell climatology (12 months + annual) and store it."""
    mod = importlib.import_module(SOURCES[source])
    if not hasattr(mod, "fetch_climatology"):
        raise NotImplementedError(f"source {source!r} has no climatology fetch")
    print(f"[1/3] Downloading {var} climatology from {source} · {region} …")
    raw = mod.fetch_climatology(var, region)
    print("[2/3] Regridding climatology …")
    grid = regrid(raw, region)
    ds_id = f"{source}_{var}_{region}_clim"
    path = GRIDDED_DIR / f"{ds_id}.nc"
    print(f"[3/3] Writing {path.name} …")
    grid.to_netcdf(path)
    nlat, nlon = grid[var].sizes["lat"], grid[var].sizes["lon"]
    entry = {
        "id": ds_id, "source": raw.attrs.get("source", source), "var": var,
        "units": VARIABLES[var]["units"], "region": region, "bbox": REGIONS[region],
        "res_deg": res_for(region), "kind": "climatology",
        "grid_shape": [nlat, nlon], "n_cells": nlat * nlon,
        "path": str(path.relative_to(GRIDDED_DIR.parent.parent)),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "ingested",
    }
    m = _load_manifest()
    m["datasets"] = [d for d in m["datasets"] if d["id"] != ds_id] + [entry]
    _save_manifest(m)
    print(f"✓ ingested climatology {ds_id}: {nlat}×{nlon} × 13 months")
    return entry


def main():
    ap = argparse.ArgumentParser(description="Bhū-Darpan national-data ingestion")
    ap.add_argument("--source", default="power", choices=list(SOURCES))
    ap.add_argument("--var", default="rain", choices=list(VARIABLES))
    ap.add_argument("--region", default="jk", choices=list(REGIONS))
    ap.add_argument("--start", help="YYYYMMDD (daily mode)")
    ap.add_argument("--end", help="YYYYMMDD (daily mode)")
    ap.add_argument("--climatology", action="store_true", help="ingest per-cell climatology instead of a daily window")
    a = ap.parse_args()
    if a.climatology:
        run_climatology(a.source, a.var, a.region)
    else:
        if not (a.start and a.end):
            ap.error("--start and --end are required unless --climatology")
        run(a.source, a.var, a.region, a.start, a.end)


if __name__ == "__main__":
    main()
