"""Multi-source data assimilation.

Fuses two independent reanalyses — NASA POWER (MERRA-2) and Open-Meteo (ERA5) — over a
region via **optimal interpolation** (inverse-error-variance weighting). Each source's
error is measured against the IMD station record; the fused estimate weights the more
accurate source more, and its fit to ground truth is (usually) better than either source
alone — demonstrating uncertainty reduction. The per-cell disagreement |POWER − ERA5| is
returned as an uncertainty (spread) field.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from ingest.config import GRIDDED_DIR
from . import climate
from .gridded_analysis import _find, _sample, markers_for


def _daily(var, region, source):
    import xarray as xr
    m = _find(var, region, False, max_days=180, source_contains=source)
    if not m:
        return None, None
    return xr.open_dataset(GRIDDED_DIR / f"{m['id']}.nc")[var], m


def _rmse(a, b):
    e = (a - b); e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e ** 2))) if e.size else float("nan")


def _overlaps(a: dict, b: dict) -> bool:
    """True if two manifest entries' [start, end] date ranges overlap (YYYYMMDD strings)."""
    return not (a["end"] < b["start"] or a["start"] > b["end"])


def _power_overlapping(var, region, om_m):
    """The POWER daily grid that overlaps the Open-Meteo period, so the two reanalyses
    being fused are contemporaneous (live refresh can push POWER ahead of Open-Meteo)."""
    import xarray as xr
    from .gridded_analysis import _manifest
    cand = [d for d in _manifest()["datasets"]
            if d["var"] == var and d["region"] == region and d.get("kind") != "climatology"
            and "power" in d.get("source", "").lower() and _overlaps(d, om_m)]
    if not cand:
        return None, None

    def _overlap_days(d):
        s, e = max(d["start"], om_m["start"]), min(d["end"], om_m["end"])
        from datetime import datetime as _dt
        return (_dt.strptime(e, "%Y%m%d") - _dt.strptime(s, "%Y%m%d")).days
    # most shared days with the Open-Meteo window, then the shortest (tightest) grid,
    # then the newest end date — so fusion always uses the current contemporaneous pair
    best = max(cand, key=lambda d: (_overlap_days(d), -d.get("days", 10 ** 9), d.get("end", "")))
    return xr.open_dataset(GRIDDED_DIR / f"{best['id']}.nc")[var], best


def available(region: str = "jk") -> list[str]:
    out = []
    for var in ("tmean", "rain"):
        if _daily(var, region, "POWER")[0] is not None and _daily(var, region, "Open-Meteo")[0] is not None:
            out.append(var)
    return out


def _pair(var, region, om_m):
    """(POWER, Open-Meteo, POWER-meta) for an Open-Meteo manifest entry, on a common grid
    and aligned to their shared dates — or (None, None, None)."""
    import xarray as xr
    power, pm = _power_overlapping(var, region, om_m)
    if power is None:
        return None, None, None
    om = xr.open_dataset(GRIDDED_DIR / f"{om_m['id']}.nc")[var]
    om = om.interp(lat=power.lat, lon=power.lon)          # ensure common grid
    power, om = xr.align(power, om, join="inner")        # shared timestamps only
    if power.time.size == 0:
        return None, None, None
    return power, om, pm


def _station_errors(var, power, om) -> dict | None:
    """Per-source RMSE vs the IMD station record at the station cell (Srinagar — a valley
    station, so comparing there avoids an all-cell elevation bias) and the resulting
    optimal-interpolation weights ∝ 1/error². None when there is no ground-truth overlap."""
    ST_LAT, ST_LON = 34.08, 74.80
    iso = np.datetime_as_string(power.time.values, unit="D")
    ps = np.asarray(power.sel(lat=ST_LAT, lon=ST_LON, method="nearest").values, float)
    os_ = np.asarray(om.sel(lat=ST_LAT, lon=ST_LON, method="nearest").values, float)
    D = climate._load()
    sidx = {d.isoformat(): i for i, d in enumerate(D.dates)}
    st = np.array([(D.temp if var == "tmean" else D.precip)[sidx[s]] if s in sidx else np.nan for s in iso])
    ok = np.isfinite(st) & np.isfinite(ps) & np.isfinite(os_)
    if ok.sum() < 5:
        return None
    ep, eo = ps[ok] - st[ok], os_[ok] - st[ok]            # raw errors vs ground truth
    # Remove each source's systematic (mean) bias for continuous variables; rainfall is
    # left unshifted (non-negative, and its bias is multiplicative rather than additive).
    debias = var != "rain"
    bp, bo = (float(ep.mean()), float(eo.mean())) if debias else (0.0, 0.0)
    dp, do = ep - bp, eo - bo
    # BLUE: minimum-variance combination using the full error covariance (errors from
    # two reanalyses are correlated, so plain 1/σ² weighting is not optimal).
    sp2, so2 = float(np.mean(dp ** 2)), float(np.mean(do ** 2))
    c = float(np.mean(dp * do))
    den = sp2 + so2 - 2 * c
    wp = float(np.clip((so2 - c) / den, 0.0, 1.0)) if den > 1e-9 else 0.5
    wo = 1.0 - wp
    rp, ro = float(np.sqrt(sp2)), float(np.sqrt(so2))
    rf = float(np.sqrt(np.mean((wp * dp + wo * do) ** 2)))
    return {"rmse_p": rp, "rmse_o": ro, "rmse_f": rf, "wp": wp, "wo": wo,
            "bias_p": bp, "bias_o": bo, "debiased": debias,
            "raw_rmse_p": _rmse(ps[ok], st[ok]), "raw_rmse_o": _rmse(os_[ok], st[ok]),
            "corr": float(c / (np.sqrt(sp2 * so2) + 1e-12)),
            "period": f"{iso[ok][0]}–{iso[ok][-1]}", "n": int(ok.sum())}


def _calibration(var, region) -> dict | None:
    """Error statistics from the newest Open-Meteo/POWER pair that overlaps the IMD station
    record. Operational optimal interpolation estimates source error variances on a
    calibration period with ground truth, then applies those weights to the live window."""
    from .gridded_analysis import _manifest
    csv_end = climate._load().dates[-1].strftime("%Y%m%d")
    cands = [d for d in _manifest()["datasets"]
             if d["var"] == var and d["region"] == region and d.get("kind") != "climatology"
             and "open-meteo" in d.get("source", "").lower() and d.get("start", "9") <= csv_end]
    for om_m in sorted(cands, key=lambda d: d.get("end", ""), reverse=True):
        power, om, _ = _pair(var, region, om_m)
        if power is None:
            continue
        st = _station_errors(var, power, om)
        if st:
            return st
    return None


@lru_cache(maxsize=8)
def fuse(var: str, region: str = "jk") -> dict | None:
    import xarray as xr
    _, om_m = _daily(var, region, "Open-Meteo")          # newest Open-Meteo window
    clim_m = _find(var, region, True, source_contains="POWER")
    if om_m is None or not clim_m:
        return None
    # the contemporaneous POWER grid (a live refresh can push POWER's window ahead)
    power, om, pm = _pair(var, region, om_m)
    if power is None:
        return None
    clim = xr.open_dataset(GRIDDED_DIR / f"{clim_m['id']}.nc")[var]
    iso = np.datetime_as_string(power.time.values, unit="D")

    # weights: validate the live window if it has IMD ground truth, else calibrate
    stats = _station_errors(var, power, om)
    calibrated = stats is None
    if calibrated:
        stats = _calibration(var, region)
    if stats is None:                                   # no ground truth anywhere
        stats = {"rmse_p": float("nan"), "rmse_o": float("nan"), "rmse_f": float("nan"),
                 "wp": 0.5, "wo": 0.5, "period": "", "n": 0}
    rmse_p, rmse_o, rmse_f = stats["rmse_p"], stats["rmse_o"], stats["rmse_f"]
    wp, wo = stats["wp"], stats["wo"]
    validated = ("IMD station record" + (f" (calibrated {stats['period']})"
                                         if calibrated and stats["period"] else ""))

    # fused time-mean field + uncertainty (spread). ERA5 is first brought onto POWER's
    # bias level (the calibrated inter-source offset) so the blend stays on the scale of
    # the POWER climatology used for the anomaly; the spread is the residual disagreement.
    pf = np.asarray(power.mean("time", skipna=True).values, float)
    of = np.asarray(om.mean("time", skipna=True).values, float)
    of_adj = of - (stats.get("bias_o", 0.0) - stats.get("bias_p", 0.0))
    fused = wp * pf + wo * of_adj
    spread = np.abs(pf - of_adj)

    months = sorted(set(int(m) for m in np.atleast_1d(power["time"].dt.month.values)))
    clim_sel = np.asarray(clim.isel(month=[m - 1 for m in months]).mean("month").values, float)
    anom = fused - clim_sel

    lats = np.asarray(power.lat.values, float)
    lons = np.asarray(power.lon.values, float)
    fin = anom[np.isfinite(anom)]
    districts = [{"name": n, "lat": la, "lon": lo,
                  "value": round(_sample(lats, lons, fused, la, lo) or 0, 2),
                  "anomaly": round(_sample(lats, lons, anom, la, lo) or 0, 2),
                  "spread": round(_sample(lats, lons, spread, la, lo) or 0, 2)}
                 for n, la, lo in markers_for(region)]

    def _r(x):
        return round(float(x), 2) if np.isfinite(x) else None
    red_vs_best = ((1 - rmse_f / min(rmse_p, rmse_o)) * 100
                   if np.isfinite(rmse_f) and np.isfinite(min(rmse_p, rmse_o)) else 0.0)
    return {
        "var": var, "region": region, "units": pm["units"], "res_deg": pm["res_deg"],
        "period": f"{iso[0]}–{iso[-1]}",
        "sources": [{"name": "NASA POWER (MERRA-2)", "rmse": _r(rmse_p), "weight": round(wp, 2)},
                    {"name": "Open-Meteo (ERA5)", "rmse": _r(rmse_o), "weight": round(wo, 2)}],
        "fused_rmse": _r(rmse_f),
        "reduction_vs_best_pct": round(red_vs_best, 1),
        "validated_against": validated,
        "calibrated": calibrated,
        "method_detail": ("BLUE (covariance-aware optimal interpolation)"
                          + (" with calibrated bias correction" if stats.get("debiased") else "")),
        "error_correlation": round(stats.get("corr", 0.0), 2),
        "lats": lats, "lons": lons,
        "anomaly": anom, "value": fused, "spread": spread,
        "amin": float(np.nanmin(fin)) if fin.size else None,
        "amax": float(np.nanmax(fin)) if fin.size else None,
        "spread_mean": round(float(np.nanmean(spread)), 2),
        "spread_max": round(float(np.nanmax(spread)), 2),
        "districts": districts,
    }
