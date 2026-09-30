"""Climate-hazard analytics computed from the real 50-year J&K daily record.

- Drought: Standardized Precipitation Index (SPI-3), standardised against the full
  1973–2023 distribution per calendar month.
- Heatwave: anomaly-based heatwave-day / event detection from daily max temperature.
- Monsoon: JJAS seasonal accumulation, onset estimate and progress vs the normal.

All three read models/jk_state_daily_50y.csv (ds, temp_mean, temp_min, temp_max, precip).
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from functools import lru_cache

import numpy as np

from ..config import settings

CSV_PATH = settings.base_dir / "models" / "jk_state_daily_50y.csv"

# Representative J&K point for the live NASA POWER tail. Temperature/precip anomalies
# transfer well across the region; the absolute level is reconstructed from the
# historical climatology below, so the point choice barely matters.
_POWER_LAT, _POWER_LON = 34.0, 75.3


def _doy_clim(values: np.ndarray, doys: np.ndarray) -> np.ndarray:
    """Day-of-year climatology (index 1..365) with a ±3-day smoothing window."""
    clim = np.zeros(366)
    for k in range(1, 366):
        m = np.abs(((doys - k + 182) % 365) - 182) <= 3
        if m.any():
            clim[k] = values[m].mean()
    return clim


@lru_cache(maxsize=1)
def _load_csv():
    dates, precip, tmax, tmin, tmean = [], [], [], [], []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                d = datetime.strptime(row["ds"][:10], "%Y-%m-%d").date()
                tx = float(row["temp_max"])
                tn = float(row.get("temp_min", tx))
                precip.append(max(0.0, float(row["precip"])))
                tmax.append(tx)
                tmin.append(tn)
                tmean.append(float(row.get("temp_mean", (tx + tn) / 2)))
                dates.append(d)
            except (ValueError, KeyError):
                continue
    return {"dates": dates, "precip": np.array(precip), "tmax": np.array(tmax),
            "tmin": np.array(tmin), "tmean": np.array(tmean)}


def _live_tail(base) -> dict | None:
    """Fetch NASA POWER daily data from the day after the CSV ends to today and
    reconstruct it on the CSV's climatological scale (day-of-year anomaly transfer),
    so it splices on continuously and the hazard indices run through the current month.
    Returns appended arrays, or None on any failure (the app then uses the CSV alone)."""
    try:
        import requests
        csv_end = base["dates"][-1]
        today = date.today()
        if today <= csv_end:
            return None
        r = requests.get(
            "https://power.larc.nasa.gov/api/temporal/daily/point",
            params={"parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR", "community": "AG",
                    "longitude": _POWER_LON, "latitude": _POWER_LAT,
                    "start": "20000101", "end": today.strftime("%Y%m%d"), "format": "JSON"},
            timeout=45)
        p = r.json()["properties"]["parameter"]
        t2m, txx, tnn, prc = p["T2M"], p["T2M_MAX"], p["T2M_MIN"], p["PRECTOTCORR"]
        keys = sorted(k for k in t2m if t2m[k] > -900 and prc.get(k, -999) > -900)
        if not keys:
            return None
        pdates = [datetime.strptime(k, "%Y%m%d").date() for k in keys]
        pdoy = np.array([min(d.timetuple().tm_yday, 365) for d in pdates])
        p_tmean = np.array([t2m[k] for k in keys])
        p_tmax = np.array([txx[k] for k in keys])
        p_tmin = np.array([tnn[k] for k in keys])
        p_prec = np.array([max(0.0, prc[k]) for k in keys])

        base_mask = np.array([d <= csv_end for d in pdates])
        if base_mask.sum() < 365:
            return None
        pc_tmean = _doy_clim(p_tmean[base_mask], pdoy[base_mask])
        pc_tmax = _doy_clim(p_tmax[base_mask], pdoy[base_mask])
        pc_tmin = _doy_clim(p_tmin[base_mask], pdoy[base_mask])
        pc_prec = _doy_clim(p_prec[base_mask], pdoy[base_mask])

        cdoy = np.array([min(d.timetuple().tm_yday, 365) for d in base["dates"]])
        cc_tmean = _doy_clim(base["tmean"], cdoy)
        cc_tmax = _doy_clim(base["tmax"], cdoy)
        cc_tmin = _doy_clim(base["tmin"], cdoy)
        cc_prec = _doy_clim(base["precip"], cdoy)

        td, tmean_, tmax_, tmin_, tprec_ = [], [], [], [], []
        for i, d in enumerate(pdates):
            if d <= csv_end:
                continue
            k = int(pdoy[i])
            tmean_.append(cc_tmean[k] + (p_tmean[i] - pc_tmean[k]))
            tmax_.append(cc_tmax[k] + (p_tmax[i] - pc_tmax[k]))
            tmin_.append(cc_tmin[k] + (p_tmin[i] - pc_tmin[k]))
            ratio = float(np.clip(cc_prec[k] / pc_prec[k], 0.2, 6.0)) if pc_prec[k] > 0.15 else 1.0
            tprec_.append(max(0.0, p_prec[i] * ratio))
            td.append(d)
        if not td:
            return None
        return {"dates": td, "precip": np.array(tprec_), "tmax": np.array(tmax_),
                "tmin": np.array(tmin_), "tmean": np.array(tmean_)}
    except Exception:
        return None


@lru_cache(maxsize=3)
def _build(_day: str):
    base = _load_csv()
    tail = _live_tail(base)
    if tail:
        dates = base["dates"] + tail["dates"]
        precip = np.concatenate([base["precip"], tail["precip"]])
        tmax = np.concatenate([base["tmax"], tail["tmax"]])
        tmin = np.concatenate([base["tmin"], tail["tmin"]])
        tmean = np.concatenate([base["tmean"], tail["tmean"]])
    else:
        dates, precip = base["dates"], base["precip"]
        tmax, tmin, tmean = base["tmax"], base["tmin"], base["tmean"]
    doy = np.array([min(d.timetuple().tm_yday, 365) for d in dates])
    year = np.array([d.year for d in dates])
    month = np.array([d.month for d in dates])
    # 1973–2023 baseline climatology (historical only, so anomalies stay comparable)
    hist = year <= 2023
    return {"dates": dates, "precip": precip, "tmax": tmax, "tmin": tmin, "tmean": tmean,
            "doy": doy, "year": year, "month": month,
            "clim_tmax": _doy_clim(tmax[hist], doy[hist]),
            "clim_tmin": _doy_clim(tmin[hist], doy[hist]),
            "live": bool(tail)}


def _data():
    return _build(date.today().isoformat())


# --------------------------------------------------------------------------- #
# Drought — SPI-3
# --------------------------------------------------------------------------- #
def _monthly_precip(D):
    """Return (ym list 'YYYY-MM', totals) monthly precipitation totals."""
    keys, tot = {}, {}
    for d, p in zip(D["dates"], D["precip"]):
        k = (d.year, d.month)
        tot[k] = tot.get(k, 0.0) + p
    ks = sorted(tot)
    return ks, np.array([tot[k] for k in ks])


def _spi(series_3mo, months):
    """Standardise 3-month sums per calendar month against the full record."""
    spi = np.full(len(series_3mo), np.nan)
    for mo in range(1, 13):
        idx = np.where(months == mo)[0]
        vals = series_3mo[idx]
        v = vals[np.isfinite(vals)]
        if v.size > 5:
            mu, sd = v.mean(), v.std() + 1e-6
            spi[idx] = (series_3mo[idx] - mu) / sd
    return np.clip(spi, -3, 3)


def _spi_class(x):
    if x <= -2: return ("Extreme drought", "#b23b1e")
    if x <= -1.5: return ("Severe drought", "#d2694a")
    if x <= -1.0: return ("Moderate drought", "#dd9138")
    if x < 1.0: return ("Near normal", "#2aa38a")
    if x < 1.5: return ("Moderately wet", "#3b9be6")
    return ("Very wet", "#2f7d9a")


def drought() -> dict:
    D = _data()
    ks, monthly = _monthly_precip(D)
    months = np.array([k[1] for k in ks])
    roll3 = np.convolve(monthly, np.ones(3), "valid")             # 3-month sums
    roll3 = np.concatenate([[np.nan, np.nan], roll3])
    spi = _spi(roll3, months)
    latest = float(spi[-1])
    label, color = _spi_class(latest)
    series = [{"t": f"{k[0]}-{k[1]:02d}", "spi": round(float(s), 2)}
              for k, s in list(zip(ks, spi))[-60:] if np.isfinite(s)]
    return {"index": "SPI-3", "as_of": f"{ks[-1][0]}-{ks[-1][1]:02d}",
            "value": round(latest, 2), "class": label, "color": color,
            "series": series,
            "note": "Standardized Precipitation Index over 3 months, 1973–2023 baseline."}


# --------------------------------------------------------------------------- #
# Heatwave detection
# --------------------------------------------------------------------------- #
def heatwave(threshold: float = 4.5, abs_min: float = 30.0) -> dict:
    D = _data()
    anom = D["tmax"] - D["clim_tmax"][D["doy"]]
    # heatwave = well above normal AND hot in absolute terms (excludes warm winters)
    hot = (anom >= threshold) & (D["tmax"] >= abs_min)
    # events = >=2 consecutive hot days
    events_days = np.zeros(len(hot), dtype=bool)
    run = 0
    for i, h in enumerate(hot):
        run = run + 1 if h else 0
        if run >= 2:
            events_days[i] = True
            events_days[i - 1] = True
    years = sorted(set(D["year"]))
    per_year = [{"year": int(y), "days": int(events_days[D["year"] == y].sum())}
                for y in years][-12:]
    recent = anom[-3:]
    active = bool(events_days[-3:].any())
    return {"threshold_c": threshold,
            "active": active,
            "status": "Heatwave conditions" if active else "No active heatwave",
            "recent_tmax_anomaly_c": round(float(recent[-1]), 1),
            "as_of": D["dates"][-1].isoformat(),
            "per_year": per_year,
            "note": f"Heatwave day = daily max ≥ {abs_min}°C and ≥ +{threshold}°C above the "
                    f"1973–2023 normal, for ≥2 consecutive days."}


# --------------------------------------------------------------------------- #
# Monsoon onset & progression (JJAS)
# --------------------------------------------------------------------------- #
def monsoon() -> dict:
    D = _data()
    years = sorted(set(D["year"]))
    last_year = years[-1]

    def season_cum(yr):
        m = (D["year"] == yr) & (np.array([d.month for d in D["dates"]]) >= 6) & \
            (np.array([d.month for d in D["dates"]]) <= 9)
        p = D["precip"][m]
        return np.cumsum(p) if p.size else np.array([])

    cur = season_cum(last_year)
    # climatological mean cumulative curve (align by day-of-season)
    all_cum = [season_cum(y) for y in years if season_cum(y).size >= 100]
    L = min(len(c) for c in all_cum)
    clim_cum = np.mean([c[:L] for c in all_cum], axis=0)
    cur = cur[:L]

    seasonal_normal = float(clim_cum[-1])
    received = float(cur[-1]) if cur.size else 0.0
    progress = round(received / (seasonal_normal + 1e-6) * 100, 0)

    # onset: first day where 7-day running rainfall >= 10 mm
    m = (D["year"] == last_year) & (np.array([d.month for d in D["dates"]]) >= 6) & \
        (np.array([d.month for d in D["dates"]]) <= 9)
    sdates = [d for d, k in zip(D["dates"], m) if k]
    sp = D["precip"][m]
    onset = None
    run7 = np.convolve(sp, np.ones(7), "valid")
    hit = np.where(run7 >= 10)[0]
    if hit.size:
        onset = sdates[hit[0]].isoformat()

    curve = [{"d": i + 1, "current": round(float(cur[i]), 1), "normal": round(float(clim_cum[i]), 1)}
             for i in range(0, L, 3)]
    return {"season": "JJAS", "year": int(last_year), "as_of": D["dates"][-1].isoformat(),
            "onset_date": onset, "progress_pct": progress,
            "received_mm": round(received, 1), "seasonal_normal_mm": round(seasonal_normal, 1),
            "curve": curve,
            "note": "Cumulative Jun–Sep rainfall vs the 1973–2023 normal; onset = first "
                    "7-day spell ≥ 10 mm."}


# --------------------------------------------------------------------------- #
# Long-term trends & extremes (all straight from the 1973–2023 record)
# --------------------------------------------------------------------------- #
def warming_trend() -> dict:
    """Annual mean temperature with a least-squares linear trend."""
    D = _data()
    years = np.array(sorted(set(int(y) for y in D["year"])))
    ann = np.array([D["tmean"][D["year"] == y].mean() for y in years])
    # exclude a partial final year from the fit so the slope isn't skewed
    full = np.array([int((D["year"] == y).sum()) >= 330 for y in years])
    yf, af = years[full], ann[full]
    slope, intercept = np.polyfit(yf, af, 1)
    fit = slope * years + intercept
    span = int(yf[-1] - yf[0]) if yf.size > 1 else 0
    return {
        "series": [{"year": int(y), "mean_c": round(float(a), 2), "trend_c": round(float(f), 2)}
                   for y, a in zip(years, ann) for f in [slope * y + intercept]],
        "slope_c_per_decade": round(float(slope) * 10, 2),
        "total_change_c": round(float(slope) * span, 2),
        "span": f"{int(yf[0])}–{int(yf[-1])}" if yf.size else "",
        "note": "Annual mean temperature, 1973–2023, with an ordinary least-squares trend.",
    }


def extreme_rain(pct: float = 95.0) -> dict:
    """Heavy-rain days per year, where a heavy day exceeds the 95th percentile of all
    wet days (a standard flood / landslide precursor index)."""
    D = _data()
    wet = D["precip"][D["precip"] >= 1.0]
    thr = float(np.percentile(wet, pct)) if wet.size else 0.0
    heavy = D["precip"] >= thr
    years = sorted(set(int(y) for y in D["year"]))
    per_year = [{"year": int(y), "days": int(heavy[D["year"] == y].sum())} for y in years]
    full_years = [p for p, y in zip(per_year, years) if int((D["year"] == y).sum()) >= 330]
    latest = full_years[-1] if full_years else per_year[-1]
    baseline = float(np.mean([p["days"] for p in full_years[:-1]])) if len(full_years) > 1 else latest["days"]
    return {
        "threshold_mm": round(thr, 1), "percentile": pct,
        "per_year": per_year[-12:],
        "latest_year": latest["year"], "latest_days": latest["days"],
        "baseline_days": round(baseline, 1),
        "note": f"Heavy-rain day = daily rainfall ≥ {round(thr,1)} mm "
                f"(the {int(pct)}th percentile of all wet days, 1973–2023).",
    }


def coldwave(threshold: float = 4.5) -> dict:
    """Frost days per year (min temp ≤ 0 °C) plus a current cold-snap flag from the
    recent minimum-temperature anomaly."""
    D = _data()
    frost = D["tmin"] <= 0.0
    years = sorted(set(int(y) for y in D["year"]))
    per_year = [{"year": int(y), "days": int(frost[D["year"] == y].sum())} for y in years]
    full_years = [p for p, y in zip(per_year, years) if int((D["year"] == y).sum()) >= 330]
    latest = full_years[-1] if full_years else per_year[-1]
    anom = D["tmin"] - D["clim_tmin"][D["doy"]]
    recent = float(anom[-3:].mean())
    active = bool(recent <= -threshold)
    return {
        "per_year": per_year[-12:],
        "latest_year": latest["year"], "latest_days": latest["days"],
        "recent_tmin_anomaly_c": round(recent, 1),
        "active": active,
        "status": "Cold-snap conditions" if active else "No active cold-wave",
        "note": f"Frost day = daily minimum ≤ 0 °C; cold-snap flag = min-temp ≥ {threshold} °C "
                "below the 1973–2023 normal.",
    }


def records() -> dict:
    """All-time daily extremes from the record — instantly explainable headline stats."""
    D = _data()
    def at(arr, i): return {"value": round(float(arr[i]), 1), "date": D["dates"][i].isoformat()}
    hot = int(np.argmax(D["tmax"]))
    cold = int(np.argmin(D["tmin"]))
    wet = int(np.argmax(D["precip"]))
    return {
        "span": f"{D['dates'][0].isoformat()} → {D['dates'][-1].isoformat()}",
        "record_days": len(D["dates"]),
        "hottest": at(D["tmax"], hot),
        "coldest": at(D["tmin"], cold),
        "wettest": at(D["precip"], wet),
    }


def analytics() -> dict:
    return {"warming": warming_trend(), "extreme_rain": extreme_rain(),
            "coldwave": coldwave(), "records": records()}


def summary() -> dict:
    return {"drought": drought(), "heatwave": heatwave(), "monsoon": monsoon()}
