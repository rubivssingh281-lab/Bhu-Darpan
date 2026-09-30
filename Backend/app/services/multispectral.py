"""Multispectral index support (NIR/SWIR) — base build for reliable flood & burn detection.

RGB alone can't separate water from shadow or a burn scar from bare rock. With NIR and SWIR
bands the standard indices become decisive:
  * NDWI  = (Green - NIR) / (Green + NIR)        > 0      -> open water (flood)
  * NDVI  = (NIR - Red)   / (NIR + Red)          low      -> stressed/loss vegetation (drought)
  * NBR   = (NIR - SWIR)  / (NIR + SWIR)         drop     -> burned area (dNBR for pre/post)

This module reads a multi-band GeoTIFF and returns these index fields + coverage fractions.
It is optional: if rasterio/tifffile aren't installed, callers fall back to the RGB detector.

Band mapping is Sentinel-2-like by default (1-indexed): B3=Green, B4=Red, B8=NIR, B12=SWIR.
Override via `bands=` for other sensors (Landsat, INSAT, drone multispectral).
"""
from __future__ import annotations

import io

import numpy as np

# Default 1-indexed band positions in the GeoTIFF (Sentinel-2 subset order).
DEFAULT_BANDS = {"green": 1, "red": 2, "nir": 3, "swir": 4}


def available() -> bool:
    try:
        import rasterio  # noqa: F401
        return True
    except Exception:
        try:
            import tifffile  # noqa: F401
            return True
        except Exception:
            return False


def _read_stack(data: bytes) -> np.ndarray | None:
    """Return a (bands, H, W) float array, or None if it can't be decoded."""
    try:
        import rasterio
        with rasterio.open(io.BytesIO(data)) as ds:
            return ds.read().astype(np.float32)
    except Exception:
        pass
    try:
        import tifffile
        arr = tifffile.imread(io.BytesIO(data)).astype(np.float32)
        if arr.ndim == 3 and arr.shape[0] > arr.shape[2]:   # (H,W,bands) -> (bands,H,W)
            arr = np.moveaxis(arr, -1, 0)
        return arr
    except Exception:
        return None


def _norm_index(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a - b) / (a + b + 1e-6)


def _stretch(band: np.ndarray) -> np.ndarray:
    """Percentile contrast-stretch a band to 0-255 uint8 for display."""
    v = band[np.isfinite(band)]
    if v.size == 0:
        return np.zeros_like(band, np.uint8)
    lo, hi = np.percentile(v, 2), np.percentile(v, 98)
    out = np.clip((band - lo) / (hi - lo + 1e-9), 0, 1) * 255
    return out.astype(np.uint8)


def preview_rgb(data: bytes, bands: dict | None = None) -> np.ndarray | None:
    """False-colour RGB preview (R=NIR, G=Red, B=Green) from a multispectral GeoTIFF,
    so scenes PIL can't decode (float/16-bit/>3-band) still render + segment."""
    bands = bands or DEFAULT_BANDS
    stack = _read_stack(data)
    if stack is None or stack.shape[0] < max(bands.values()):
        return None
    nir, red, green = stack[bands["nir"] - 1], stack[bands["red"] - 1], stack[bands["green"] - 1]
    return np.dstack([_stretch(nir), _stretch(red), _stretch(green)])


def indices(data: bytes, bands: dict | None = None, thr=0.0) -> dict | None:
    """Compute NDWI/NDVI/NBR fields + coverage fractions from a multispectral GeoTIFF.

    Returns None when the file can't be read or lacks enough bands, so the caller
    gracefully falls back to the RGB detector.
    """
    bands = bands or DEFAULT_BANDS
    stack = _read_stack(data)
    if stack is None or stack.shape[0] < max(bands.values()):
        return None

    def band(name):
        return stack[bands[name] - 1]

    green, red, nir, swir = band("green"), band("red"), band("nir"), band("swir")
    # normalized-difference indices are invariant to linear scale, so raw DN or reflectance
    # both work without rescaling. nodata = pixels where every band is ~0.
    valid = ~((np.abs(green) + np.abs(red) + np.abs(nir) + np.abs(swir)) < 1e-6)

    ndwi = _norm_index(green, nir)     # McFeeters water index
    mndwi = _norm_index(green, swir)   # modified NDWI — better water vs built-up
    ndvi = _norm_index(nir, red)
    nbr = _norm_index(nir, swir)       # burn (dNBR with a pre-event scene is the gold standard)
    nbr2 = _norm_index(swir, red)

    water = ((ndwi > thr) | (mndwi > thr)) & valid
    veg = (ndvi > 0.3) & valid
    burn = (nbr < -0.1) & (ndvi < 0.3) & valid   # low NBR + low vegetation -> burned
    # Active fire: SWIR reflectance spikes above NIR at a hot flame front (thermal anomaly).
    active_fire = (swir > nir + 0.10) & (swir > 0.15) & (ndvi < 0.25) & valid
    n = max(int(valid.sum()), 1)

    def pct(m):
        return round(100.0 * float(np.count_nonzero(m)) / n, 1)

    def mean(a):
        v = a[valid]
        return round(float(np.nanmean(v)), 3) if v.size else 0.0

    return {
        "source": "multispectral",
        "water_pct": pct(water), "veg_pct": pct(veg), "burn_pct": pct(burn),
        "active_fire_pct": pct(active_fire),
        "ndwi_mean": mean(ndwi), "mndwi_mean": mean(mndwi),
        "ndvi_mean": mean(ndvi), "nbr_mean": mean(nbr), "nbr2_mean": mean(nbr2),
        "shape": [int(stack.shape[1]), int(stack.shape[2])],
        "valid_pct": round(100.0 * n / ndwi.size, 1),
        "masks": {"water": water, "veg": veg, "burn": burn, "fire": active_fire},
        "note": "NDWI/MNDWI (flood), NDVI (drought) and NBR/NBR2 (burn) from NIR+SWIR bands "
                "— decisive vs RGB. Supply a pre-event scene for dNBR burn severity.",
    }


def dnbr(pre: bytes, post: bytes, bands: dict | None = None) -> dict | None:
    """Burn severity from pre/post NBR difference (dNBR) — the standard wildfire metric."""
    a, b = indices(pre, bands), indices(post, bands)
    if not a or not b:
        return None
    delta = a["nbr_mean"] - b["nbr_mean"]           # positive => vegetation burned
    sev = ("Unburned" if delta < 0.1 else "Low" if delta < 0.27
           else "Moderate" if delta < 0.66 else "High")
    return {"dnbr": round(float(delta), 3), "severity": sev,
            "note": "USGS dNBR thresholds: <0.1 unburned, 0.1-0.27 low, 0.27-0.66 moderate, >0.66 high."}
