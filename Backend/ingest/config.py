"""ETL configuration: regions, canonical variables, common grid, storage paths."""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
GRIDDED_DIR = BASE_DIR / "data" / "gridded"
GRIDDED_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST = GRIDDED_DIR / "manifest.json"

# Common target grid resolution (degrees) — IMD rainfall native is 0.25°.
COMMON_RES = 0.25

# Pilot / national bounding boxes: (lat_min, lat_max, lon_min, lon_max)
REGIONS = {
    "jk": (32.0, 37.0, 73.0, 80.0),      # Jammu & Kashmir + Ladakh
    "india": (6.5, 38.5, 66.5, 100.0),   # national
}

# Per-region target grid resolution (national kept coarser to stay light).
RES = {"jk": 0.25, "india": 0.5}


def res_for(region: str) -> float:
    return RES.get(region, COMMON_RES)

# Canonical variables the twin understands, and their per-source parameter codes.
# units are what we standardise to.
VARIABLES = {
    "tmean": {"units": "degC", "long_name": "Mean 2m air temperature",
              "power": "T2M", "imd": "tmean", "openmeteo": "temperature_2m_mean"},
    "tmax":  {"units": "degC", "long_name": "Maximum 2m air temperature",
              "power": "T2M_MAX", "imd": "tmax", "openmeteo": "temperature_2m_max"},
    "tmin":  {"units": "degC", "long_name": "Minimum 2m air temperature",
              "power": "T2M_MIN", "imd": "tmin", "openmeteo": "temperature_2m_min"},
    "rain":  {"units": "mm/day", "long_name": "Precipitation",
              "power": "PRECTOTCORR", "imd": "rain", "openmeteo": "precipitation_sum"},
    # Satellite-derived land-surface (skin) temperature. Ground source is INSAT
    # 3RIMG_L2B_LST via MOSDAC (see ingest/sources/mosdac.py); NASA POWER's TS
    # (Earth skin temperature) is the open, credential-free stand-in used to run
    # the surface-temperature fusion end-to-end.
    "lst":   {"units": "degC", "long_name": "Land surface temperature (satellite skin temp)",
              "power": "TS", "imd": None, "openmeteo": None},
}
