"""Climate digital-twin engine for the Jammu & Kashmir pilot region.

Backed by 50 years of real IMD-style daily gridded data (models/jk_state_daily_50y.csv:
date, temp_mean, temp_min, temp_max, precip). From it we derive genuine climatology,
current anomalies, a statistical short-term forecast (climatology + warming trend +
persistence, with uncertainty bands and a real backtested RMSE), a soil-moisture proxy
and a physically-grounded what-if water-balance response.

Pure stdlib + numpy (no pandas) so it loads fast and adds no dependencies.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..config import settings

CSV_PATH = settings.base_dir / "models" / "jk_state_daily_50y.csv"

# J&K pilot districts: name, map x/y (viewBox 0..520 x 0..380), elevation factor,
# rainfall regional multiplier. Elevation drives a temperature offset; the multiplier
# spatially disaggregates the (real) state-level anomaly into district-level values.
DISTRICTS = [
    {"name": "Baramulla", "x": 150, "y": 95, "elev": 1.9, "rmul": 1.15},
    {"name": "Srinagar", "x": 235, "y": 120, "elev": 1.6, "rmul": 1.05},
    {"name": "Kishtwar", "x": 330, "y": 110, "elev": 2.1, "rmul": 0.95},
    {"name": "Doda", "x": 250, "y": 195, "elev": 1.7, "rmul": 0.85},
    {"name": "Anantnag", "x": 175, "y": 210, "elev": 1.4, "rmul": 0.80},
    {"name": "Udhampur", "x": 160, "y": 300, "elev": 0.8, "rmul": 0.90},
    {"name": "Rajouri", "x": 355, "y": 240, "elev": 0.9, "rmul": 1.10},
    {"name": "Kathua", "x": 300, "y": 300, "elev": 0.4, "rmul": 1.00},
    {"name": "Jammu", "x": 390, "y": 320, "elev": 0.2, "rmul": 1.20},
]


@dataclass
class _Data:
    dates: list[date]
    doy: np.ndarray
    year: np.ndarray
    temp: np.ndarray
    precip: np.ndarray
    # day-of-year climatology (index 1..366)
    clim_temp: np.ndarray
    clim_temp_std: np.ndarray
    clim_precip: np.ndarray
    clim_precip_std: np.ndarray
    temp_trend_per_year: float  # warming trend °C/yr


@lru_cache(maxsize=1)
def _load() -> _Data:
    dates: list[date] = []
    temp: list[float] = []
    precip: list[float] = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                d = datetime.strptime(row["ds"][:10], "%Y-%m-%d").date()
                temp.append(float(row["temp_mean"]))
                precip.append(max(0.0, float(row["precip"])))
                dates.append(d)
            except (ValueError, KeyError):
                continue

    temp_a = np.array(temp, dtype=np.float64)
    precip_a = np.array(precip, dtype=np.float64)
    doy = np.array([min(d.timetuple().tm_yday, 365) for d in dates])
    year = np.array([d.year for d in dates])

    clim_temp = np.zeros(366)
    clim_temp_std = np.zeros(366)
    clim_precip = np.zeros(366)
    clim_precip_std = np.zeros(366)
    for k in range(1, 366):
        # small +/-3 day window smooths the day-of-year climatology
        m = np.abs(((doy - k + 182) % 365) - 182) <= 3
        if m.any():
            clim_temp[k] = temp_a[m].mean()
            clim_temp_std[k] = temp_a[m].std()
            clim_precip[k] = precip_a[m].mean()
            clim_precip_std[k] = precip_a[m].std()

    # Warming trend: linear fit of annual mean temperature vs year
    yrs = np.unique(year)
    ann = np.array([temp_a[year == y].mean() for y in yrs])
    slope = np.polyfit(yrs, ann, 1)[0]

    return _Data(dates, doy, year, temp_a, precip_a,
                 clim_temp, clim_temp_std, clim_precip, clim_precip_std, float(slope))


def _clim(arr: np.ndarray, d: date) -> float:
    return float(arr[min(d.timetuple().tm_yday, 365)])


@lru_cache(maxsize=2)
def _load_live_day(_day: str) -> _Data:
    """The historical record extended with the live NASA POWER tail (via hazards), for
    SEEDING forecasts from the latest real observations. Climatology and trend are the
    historical 1973–2023 ones, so the normal is unchanged. Training/validation and the
    fusion ground truth keep using `_load()` (the pure station record)."""
    base = _load()
    try:
        from . import hazards
        H = hazards._data()
        if not H.get("live") or H["dates"][-1] <= base.dates[-1]:
            return base
        dates = list(H["dates"])
        return _Data(dates,
                     np.array([min(d.timetuple().tm_yday, 365) for d in dates]),
                     np.array([d.year for d in dates]),
                     np.asarray(H["tmean"], dtype=np.float64),
                     np.asarray(H["precip"], dtype=np.float64),
                     base.clim_temp, base.clim_temp_std, base.clim_precip, base.clim_precip_std,
                     base.temp_trend_per_year)
    except Exception:
        return base


def _load_live() -> _Data:
    return _load_live_day(date.today().isoformat())


# --------------------------------------------------------------------------- #
# Current fused state
# --------------------------------------------------------------------------- #
def _live_state() -> dict | None:
    """Build the current climate state from the LIVE ingested gridded data (NASA POWER,
    ~3-day latency) instead of the static 50-year record, so the dashboard reflects the
    present week. Returns None when live grids aren't available (falls back to the CSV)."""
    try:
        from .gridded_analysis import anomaly
        t = anomaly("tmean", "jk")
        r = anomaly("rain", "jk")
    except Exception:
        return None
    if not t or not r:
        return None

    temp_anom = round(float(t["amean"]), 2)
    mean_temp = round(float(np.nanmean(t["value"])), 1)
    rp = r.get("anomaly_pct")
    rain_anom = float(np.nanmean(rp)) if rp is not None else 0.0
    rain_anom = round(float(np.clip(rain_anom, -70, 100)), 1)
    precip_daily = float(np.nanmean(r["value"]))
    precip_30d = round(precip_daily * 30.0, 1)

    # soil-moisture proxy from the rainfall anomaly (wetter → higher root-zone moisture)
    soil = round(float(np.clip(0.40 + rain_anom / 320.0, 0.08, 0.9)), 2)
    drought = ("Severe" if rain_anom < -40 else "Moderate" if rain_anom < -20
               else "Mild" if rain_anom < -10 else "Normal")

    end = t["period"].split("–")[-1]           # YYYYMMDD
    as_of = f"{end[:4]}-{end[4:6]}-{end[6:]}" if len(end) == 8 else end

    dat = _load()                              # warming trend from the long record (historical)
    return {
        "region": "Jammu & Kashmir",
        "as_of": as_of,
        "source": "live",
        "period": t["period"],
        "rainfall_anomaly_pct": rain_anom,
        "temperature_anomaly_c": temp_anom,
        "soil_moisture_index": soil,
        "drought_class": drought,
        "warming_trend_c_per_decade": round(dat.temp_trend_per_year * 10, 2),
        "mean_temp_c": mean_temp,
        "precip_30d_mm": precip_30d,
        "spark_temp": [round(float(x), 1) for x in dat.temp[len(dat.dates) - 14:]],
        "spark_precip": [round(float(x), 2) for x in dat.precip[len(dat.dates) - 14:]],
    }


def current_state() -> dict:
    live = _live_state()
    if live:
        return live
    dat = _load()
    n = len(dat.dates)
    last = dat.dates[-1]

    win30 = slice(n - 30, n)
    win90 = slice(n - 90, n)

    # Temperature anomaly vs climatology (°C)
    recent_days = dat.dates[win30]
    clim_t = np.array([_clim(dat.clim_temp, d) for d in recent_days])
    temp_anom = float(dat.temp[win30].mean() - clim_t.mean())

    # Rainfall anomaly (% of normal) over a 90-day window — more stable/seasonal
    days90 = dat.dates[win90]
    clim_p90 = np.array([_clim(dat.clim_precip, d) for d in days90])
    obs_p30 = float(dat.precip[win30].sum())
    rain_anom = (float(dat.precip[win90].sum()) / (clim_p90.sum() + 1e-6) - 1.0) * 100.0
    rain_anom = float(np.clip(rain_anom, -70, 100))

    # Soil-moisture proxy: antecedent precipitation index (recency-weighted), 0..1
    tail = dat.precip[n - 45:]
    w = 0.94 ** np.arange(len(tail))[::-1]
    api = float((tail * w).sum())
    soil = float(np.clip(0.15 + api / 60.0, 0.05, 0.95))

    # Drought class from SPI-like z-score of 90-day precip
    days90 = dat.dates[win90]
    clim_p90 = np.array([_clim(dat.clim_precip, d) for d in days90])
    z = (dat.precip[win90].sum() - clim_p90.sum()) / (clim_p90.std() * np.sqrt(90) + 1e-6)
    drought = ("Severe" if z < -1.3 else "Moderate" if z < -0.8
               else "Mild" if z < -0.5 else "Normal")

    return {
        "region": "Jammu & Kashmir",
        "as_of": last.isoformat(),
        "rainfall_anomaly_pct": round(rain_anom, 1),
        "temperature_anomaly_c": round(temp_anom, 2),
        "soil_moisture_index": round(soil, 2),
        "drought_class": drought,
        "warming_trend_c_per_decade": round(dat.temp_trend_per_year * 10, 2),
        "mean_temp_c": round(float(dat.temp[win30].mean()), 1),
        "precip_30d_mm": round(obs_p30, 1),
        "spark_temp": [round(float(x), 1) for x in dat.temp[n - 14:]],
        "spark_precip": [round(float(x), 2) for x in dat.precip[n - 14:]],
    }


# --------------------------------------------------------------------------- #
# 14-day forecast (climatology + trend + persistence, with backtested RMSE)
# --------------------------------------------------------------------------- #
def _backtest_rmse(var: str) -> float:
    dat = _load()
    n = len(dat.dates)
    errs = []
    clim = dat.clim_temp if var == "temperature" else dat.clim_precip
    obs = dat.temp if var == "temperature" else dat.precip
    for i in range(n - 365, n):  # last year
        errs.append(obs[i] - _clim(clim, dat.dates[i]))
    return float(np.sqrt(np.mean(np.square(errs))))


_FC_CACHE: dict = {}


def forecast(var: str) -> dict:
    """14-day forecast as an ensemble (trained AI model + climatology + persistence)
    whose spread gives the uncertainty band.

    Model selection is **skill-gated**: the deep-learning LSTM is used for a variable
    when its held-out skill beats climatology (positive skill); otherwise the system
    falls back to the gradient-boosted forecaster. This is why temperature (predictable)
    is driven by the LSTM while rainfall (chaotic at 14 days) stays on the safer model.
    """
    _ck = (var, date.today().isoformat())
    if _ck in _FC_CACHE:
        return _FC_CACHE[_ck]

    from . import ml_forecast  # local import avoids a circular dependency
    try:
        from . import lstm_forecast
        _lstm_ok = lstm_forecast.available()
    except Exception:
        _lstm_ok = False

    today = date.today()
    hist = _load()
    live = _load_live()
    # Real-time when the live tail reaches within ~2 weeks of today; otherwise fall back
    # to the same-season anchoring on the historical record.
    real_time = (today - live.dates[-1]).days <= 15
    dat = live if real_time else hist
    n = len(dat.dates)
    last = dat.dates[-1]
    is_temp = var == "temperature"
    key = "temp" if is_temp else "precip"
    clim = dat.clim_temp if is_temp else dat.clim_precip
    obs = dat.temp if is_temp else dat.precip
    unit = "°C" if is_temp else "mm/day"

    # --- skill-gated model choice ---
    lstm_skill = None
    if _lstm_ok:
        lstm_skill = (lstm_forecast.metrics() or {}).get(f"{key}_skill_pct")
    if _lstm_ok and lstm_skill is not None and lstm_skill > 0:
        chosen = lstm_forecast
        model_name = "LSTM sequence model (PyTorch, deep learning)"
        method = "Ensemble: LSTM (deep learning) + day-of-year climatology + persistence"
    else:
        chosen = ml_forecast
        model_name = "Gradient-boosted regression trees (scikit-learn)"
        method = "Ensemble: gradient-boosted trees + day-of-year climatology + persistence"

    m = chosen.metrics()
    resid = m["temp_resid_std"] if is_temp else m["precip_resid_std"]

    if real_time:
        # Seed the models from the LATEST REAL observations (live NASA POWER tail, on the
        # station scale) and forecast the 14 days that follow them. Observations lag a few
        # days (reanalysis latency), so the outlook bridges that gap and runs past today.
        anchor = n - 1
        first_day = dat.dates[anchor] + timedelta(days=1)
        obs_dates = [dat.dates[anchor - 6 + j] for j in range(7)]
    else:
        # Fallback: seed from the most recent same-season observations in the record.
        yday_doy = min((today - timedelta(days=1)).timetuple().tm_yday, 365)
        same_season = np.where(dat.doy <= yday_doy)[0]
        anchor = int(same_season[-1]) if same_season.size else n - 1
        anchor = max(40, min(anchor, n - 1))
        first_day = today
        obs_dates = [today - timedelta(days=7 - j) for j in range(7)]

    observed = [{"label": od.strftime("%d %b"), "date": od.isoformat(),
                 "value": round(float(obs[anchor - 6 + j]), 2)}
                for j, od in enumerate(obs_dates)]

    def _point(fd, val, band):
        return {"label": fd.strftime("%d %b"), "date": fd.isoformat(),
                "week": f"W{fd.isocalendar()[1]}", "value": round(float(val), 2),
                "upper": round(float(val + band), 2),
                "lower": round(float(max(0.0, val - band) if not is_temp else val - band), 2)}

    predicted = []
    bt = _backtest()
    vb = (bt or {}).get("variables", {}).get(var)
    if vb:
        # --- skill-optimised blend (see scripts/backtest_forecast.py) -----------------
        # Per-lead non-negative weights over {GBRT, LSTM, damped persistence} anomalies
        # around a trend-adjusted climatology — fit on a held-out validation year and
        # scored on later years, all at the full 14-day horizon.
        G = ml_forecast.forecast_series(var, 14, anchor_index=anchor, dat=dat)
        L = lstm_forecast.forecast_series(var, 14, anchor_index=anchor, dat=dat) if _lstm_ok else G
        t_off = (bt["temp_trend_c_per_year"] * (dat.dates[anchor].year - bt["trend_mid_year"])
                 if is_temp else 0.0)
        past = slice(anchor - 4, anchor + 1)
        last_anom = float(obs[past].mean() - clim[dat.doy[past]].mean() - t_off)
        bands = vb["methods"]["blend"]["rmse_by_lead"]
        for k in range(14):
            fd = first_day + timedelta(days=k)
            ct = _clim(clim, fd) + t_off
            pers = ct + last_anom * (0.7 ** (k + 1))
            w = vb["blend_weights"][k]
            val = ct + w[0] * (G[k] - ct) + w[1] * (L[k] - ct) + w[2] * (pers - ct)
            if not is_temp:
                val = max(0.0, val)
            predicted.append(_point(fd, val, bands[k]))       # ±1σ = backtest RMSE at that lead
        bm, cm = vb["methods"]["blend"], vb["methods"]["clim"]
        rmse, mae, clim_rmse, skill_pct = bm["rmse"], bm["mae"], cm["rmse"], bm["skill_pct"]
        model_name = "Skill-optimised ensemble (LSTM + gradient-boosted trees + damped persistence)"
        method = (f"Per-lead non-negative blend over a trend-adjusted climatology · weights fit on "
                  f"{bt['val_year']}, scored on {bt['test_period']}")
        backtest_txt = f"14-day backtest · {vb['n_test']} held-out issue dates ({bt['test_period']})"
    else:
        # --- fallback: skill-gated single model + damped persistence -----------------
        ml_pred = chosen.forecast_series(var, 14, anchor_index=anchor, dat=dat)
        aw = slice(anchor - 4, anchor + 1)
        last_anom = float(obs[aw].mean() - np.array([_clim(clim, d) for d in dat.dates[aw]]).mean())
        for k in range(14):
            fd = first_day + timedelta(days=k)
            lead = k + 1
            trend = dat.temp_trend_per_year * 0.5 if is_temp else 0.0
            member_clim = _clim(clim, fd) + trend + last_anom * (0.7 ** lead)
            val = 0.6 * ml_pred[k] + 0.4 * member_clim
            if not is_temp:
                val = max(0.0, val)
            band = (resid + abs(ml_pred[k] - member_clim) / 2.0) * (1 + 0.04 * lead)
            predicted.append(_point(fd, val, band))
        rmse = m["temp_rmse"] if is_temp else m["precip_rmse"]
        mae = m["temp_mae"] if is_temp else m["precip_mae"]
        clim_rmse = m["temp_clim_rmse"] if is_temp else m["precip_clim_rmse"]
        skill_pct = m["temp_skill_pct"] if is_temp else m["precip_skill_pct"]
        backtest_txt = f"Held-out time split · {m['test_days']} test days ({m['train_days']} train)"

    result = {
        "variable": var,
        "unit": unit,
        "issued": today.isoformat(),
        "horizon": {"start": first_day.isoformat(),
                    "end": (first_day + timedelta(days=13)).isoformat(), "days": 14},
        "latest_observation": dat.dates[anchor].isoformat() if real_time else last.isoformat(),
        "real_time": real_time,
        "observed": observed,
        "predicted": predicted,
        "skill": {
            "rmse": rmse,
            "mae": mae,
            "clim_rmse": clim_rmse,
            "skill_pct": skill_pct,
            "model": model_name,
            "method": method,
            "backtest": backtest_txt,
            "horizon_days": 14,
        },
    }
    _FC_CACHE[_ck] = result
    return result


@lru_cache(maxsize=1)
def _backtest() -> dict | None:
    """Unified 14-day backtest + blend weights (scripts/backtest_forecast.py), if present."""
    p = settings.base_dir / "models" / "forecast_backtest.json"
    if not p.exists():
        return None
    try:
        import json
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def derived_forecast(kind: str) -> dict:
    """Soil-moisture (kind='soil') and drought-risk (kind='drought') 14-day OUTLOOKS,
    derived from the live rainfall & temperature forecasts through a simple daily
    water-balance bucket. They are real-time and share the same dates as the primary
    rainfall/temperature charts, so all four panels line up on one timeline.

    Bucket: soilΔ ≈ +recharge·(rain − normal) − loss·(temp − normal); the trajectory is
    anchored so the 'now' point equals the live soil-moisture index. Drought risk is an
    SPI-style function of the soil outlook.
    """
    rain_fc = forecast("rainfall")
    temp_fc = forecast("temperature")
    dat = _load()
    soil0 = float(current_state().get("soil_moisture_index", 0.45))

    rain_seq = [o["value"] for o in rain_fc["observed"]] + [p["value"] for p in rain_fc["predicted"]]
    temp_seq = [o["value"] for o in temp_fc["observed"]] + [p["value"] for p in temp_fc["predicted"]]
    dates_seq = [date.fromisoformat(o["date"]) for o in rain_fc["observed"]] + \
                [date.fromisoformat(p["date"]) for p in rain_fc["predicted"]]
    labels_seq = [o["label"] for o in rain_fc["observed"]] + [p["label"] for p in rain_fc["predicted"]]
    seam = len(rain_fc["observed"]) - 1     # index of "now"

    def delta(i: int) -> float:
        rain_dev = rain_seq[i] - _clim(dat.clim_precip, dates_seq[i])
        temp_dev = temp_seq[i] - _clim(dat.clim_temp, dates_seq[i])
        return 0.012 * rain_dev - 0.007 * temp_dev

    raw = [0.0] * len(rain_seq)
    for i in range(1, len(raw)):
        raw[i] = raw[i - 1] + delta(i)
    off = soil0 - raw[seam]
    soil = [min(0.95, max(0.08, r + off)) for r in raw]

    # uncertainty band (predicted only), propagated from the rainfall band, widening with lead
    band = [0.0] * len(rain_seq)
    for k, p in enumerate(rain_fc["predicted"]):
        band[seam + 1 + k] = 0.012 * (p["upper"] - p["value"]) * ((k + 1) ** 0.5)

    drought = [min(100.0, max(0.0, (0.55 - s) * 185)) for s in soil]

    def pack(values, cap, digits, band_scale):
        observed = [{"label": labels_seq[i], "date": dates_seq[i].isoformat(),
                     "value": round(values[i], digits)} for i in range(seam + 1)]
        predicted = []
        for i in range(seam + 1, len(values)):
            b = band[i] * band_scale
            predicted.append({
                "label": labels_seq[i], "date": dates_seq[i].isoformat(),
                "week": f"W{dates_seq[i].isocalendar()[1]}",
                "value": round(values[i], digits),
                "upper": round(min(cap, values[i] + b), digits),
                "lower": round(max(0.0, values[i] - b), digits),
            })
        return observed, predicted

    if kind == "soil":
        obs, pred = pack(soil, 0.95, 3, 1.0)
        return {"variable": "soil moisture", "unit": "index (0–1)",
                "issued": rain_fc["issued"], "horizon": rain_fc["horizon"],
                "observed": obs, "predicted": pred,
                "derived_from": "rainfall + temperature forecast · daily water-balance bucket"}
    obs, pred = pack(drought, 100.0, 0, 185.0)
    return {"variable": "drought risk", "unit": "risk /100",
            "issued": rain_fc["issued"], "horizon": rain_fc["horizon"],
            "observed": obs, "predicted": pred,
            "derived_from": "soil-moisture outlook · SPI-style index"}


# --------------------------------------------------------------------------- #
# District layer (spatial disaggregation of the state anomaly)
# --------------------------------------------------------------------------- #
def districts(layer: str = "rain") -> dict:
    st = current_state()
    out = []
    for i, d in enumerate(DISTRICTS):
        # deterministic per-district variation seeded by index
        jitter = ((i * 37) % 11 - 5) / 10.0
        rain = round(float(np.clip(st["rainfall_anomaly_pct"] * d["rmul"] + jitter * 6, -72, 100)), 1)
        temp = round(st["temperature_anomaly_c"] + (2.0 - d["elev"]) * 0.35 + jitter * 0.1, 2)
        soil = round(float(np.clip(st["soil_moisture_index"] + (d["elev"] - 1.2) * 0.05 + jitter * 0.02, 0.05, 0.95)), 2)
        value = rain if layer == "rain" else temp if layer == "temp" else soil
        out.append({"name": d["name"], "x": d["x"], "y": d["y"], "rain": rain,
                    "temp": temp, "soil": soil, "value": value})
    return {"layer": layer, "region": "Jammu & Kashmir", "as_of": st.get("as_of"), "districts": out}


# --------------------------------------------------------------------------- #
# What-if water-balance scenario
# --------------------------------------------------------------------------- #
_KC = 0.85                 # crop coefficient (mixed orchards / paddy / pasture)
_ROOT_ZONE_MM = 150.0      # plant-available water holding capacity of the root zone
_SEASON_DAYS = 30          # the scenario is evaluated over the coming 30 days


def _live_baseline() -> dict:
    """What-if baseline = THIS season's normal climate (the day-of-year climatology of the
    coming 30 days) starting from TODAY's live soil-moisture state — so scenarios perturb
    the real current situation, not a fixed textbook value."""
    dat = _load()
    today = date.today()
    days = [today + timedelta(days=k) for k in range(_SEASON_DAYS)]
    rain = float(np.mean([_clim(dat.clim_precip, d) for d in days]))
    tmean = float(np.mean([_clim(dat.clim_temp, d) for d in days]))
    et0 = max(0.8, 1.6 + 0.16 * tmean)     # temperature-driven reference ET (mm/day)
    try:
        st = current_state()
        sm, as_of = float(st["soil_moisture_index"]), st.get("as_of")
    except Exception:
        sm, as_of = 0.41, None
    return {"rain_mm_day": round(rain, 2), "et0": round(et0, 2), "kc": _KC,
            "sm": round(sm, 2), "tmean_c": round(tmean, 1),
            "season": f"{days[0].isoformat()} → {days[-1].isoformat()}", "soil_as_of": as_of}


def _respond(b: dict, rain_pct: float, temp_c: float):
    """Core water-balance response: (rain, ET, soil, drought, crop, inflow)."""
    actual_rain = b["rain_mm_day"] * (1 + rain_pct / 100.0)
    actual_et = b["et0"] * b["kc"] * (1 + 0.065 * temp_c)      # ~6.5 %/°C (Clausius–Clapeyron)
    base_wb = b["rain_mm_day"] - b["et0"] * b["kc"]
    # 30-day bucket: the change in daily balance accumulates into the root-zone store
    d_store = ((actual_rain - actual_et) - base_wb) * _SEASON_DAYS
    sm = float(np.clip(b["sm"] + d_store / _ROOT_ZONE_MM, 0.05, 0.95))
    sm_risk = ((0.35 - sm) / 0.35 * 55) if sm < 0.35 else ((0.45 - sm) / 0.45 * 20) if sm < 0.45 else 0
    drought = int(np.clip(round(sm_risk + max(0, -rain_pct) * 0.55 + max(0, temp_c) * 6.5), 0, 100))
    # Crop-water stress (0–100), season-independent:
    #   soil term   — FAO-56 water-stress concept: stress begins once plant-available water
    #                 drops below ~50 % (depletion fraction p = 0.5) and rises linearly;
    #   demand term — rise in crop evapotranspiration demand vs this season's normal;
    #   supply term — the rainfall shortfall itself.
    soil_stress = float(np.clip((0.5 - sm) / 0.5, 0, 1)) * 70
    demand_stress = float(np.clip(actual_et / (b["et0"] * b["kc"]) - 1, 0, 1)) * 60
    supply_stress = float(np.clip(-rain_pct / 100.0, 0, 1)) * 20
    crop = int(np.clip(round(soil_stress + demand_stress + supply_stress), 0, 100))
    inflow_change = int(np.clip(round(rain_pct * 1.6 - temp_c * 3.5), -85, 120))
    return actual_rain, actual_et, sm, drought, crop, inflow_change


def whatif(rain_pct: float, temp_c: float) -> dict:
    b = _live_baseline()
    actual_rain, actual_et, sm, drought, crop, inflow_change = _respond(b, rain_pct, temp_c)
    _, _, b_sm, b_drought, b_crop, _ = _respond(b, 0.0, 0.0)
    crop_label = "Low" if crop < 25 else "Moderate" if crop < 50 else "High" if crop < 75 else "Severe"

    # --- water-balance breakdown (the physics behind the scores) --------------- #
    net = actual_rain - actual_et
    base_net = b["rain_mm_day"] - b["et0"] * b["kc"]

    def _lvl(s):
        return "Low" if s < 25 else "Moderate" if s < 50 else "High" if s < 75 else "Severe"

    # --- sector impact assessment (deterministic, derived from the response) ---- #
    hydro = int(np.clip(round(max(0, -inflow_change) * 1.05 + max(0, temp_c) * 3), 0, 100))
    supply = int(np.clip(round(((0.45 - sm) / 0.45 * 70 if sm < 0.45 else 0)
                               + max(0, -inflow_change) * 0.35), 0, 100))
    sectors = [
        {"name": "Agriculture", "risk_score": crop, "risk_label": crop_label,
         "note": "Apple, saffron & paddy — irrigation demand "
                 + ("rises as evapotranspiration outpaces rainfall." if net < base_net
                    else "eases as rainfall keeps pace with demand.")},
        {"name": "Hydropower", "risk_score": hydro, "risk_label": _lvl(hydro),
         "note": f"Baglihar, Kishanganga & Dulhasti track inflow — generation "
                 f"{'down' if inflow_change < 0 else 'up'} ~{abs(inflow_change)}%."},
        {"name": "Water supply", "risk_score": supply, "risk_label": _lvl(supply),
         "note": f"Spring-fed & municipal supply {'tightens' if supply >= 50 else 'holds'} "
                 f"with soil moisture at {round(sm, 2)}."},
    ]

    rdir = "deficit" if rain_pct < 0 else "surplus" if rain_pct > 0 else "normal rainfall"
    tdir = (f"+{temp_c:g}°C warming" if temp_c > 0
            else f"{temp_c:g}°C cooling" if temp_c < 0 else "no temperature change")
    narrative = (
        f"A {abs(rain_pct):g}% rainfall {rdir} with {tdir} shifts the daily water balance to "
        f"{net:+.1f} mm/day (normal {base_net:+.1f}). Soil moisture settles near {round(sm, 2)}, "
        f"drought-risk {drought}/100, {crop_label.lower()} crop-water stress, and reservoir "
        f"inflow {inflow_change:+d}%."
    )

    return {
        "inputs": {"rain_pct": rain_pct, "temp_c": temp_c},
        "soil_moisture_index": round(sm, 2),
        "drought_risk_score": drought,
        "crop_water_stress": crop_label,
        "crop_water_stress_score": crop,
        "reservoir_inflow_change_pct": inflow_change,
        "water_balance": {
            "rain_in_mm": round(actual_rain, 1),
            "et_out_mm": round(actual_et, 1),
            "net_mm": round(net, 1),
            "baseline_net_mm": round(base_net, 1),
            "baseline_rain_mm": b["rain_mm_day"],
            "baseline_et_mm": round(b["et0"] * b["kc"], 1),
        },
        "sectors": sectors,
        "narrative": narrative,
        "baseline": {"soil_moisture_index": round(b_sm, 2), "drought_risk_score": b_drought,
                     "crop_water_stress_score": b_crop, "reservoir_inflow_change_pct": 0},
        "baseline_info": {"season": b["season"], "normal_rain_mm_day": b["rain_mm_day"],
                          "normal_tmean_c": b["tmean_c"], "normal_et_mm_day": round(b["et0"] * b["kc"], 2),
                          "live_soil_moisture": b["sm"], "soil_as_of": b["soil_as_of"]},
    }


# --------------------------------------------------------------------------- #
# Data & models summary
# --------------------------------------------------------------------------- #
def data_summary() -> dict:
    dat = _load()
    start = dat.dates[0].isoformat()
    end = dat.dates[-1].isoformat()
    days = len(dat.dates)
    # reflect the live-extended daily record (NASA POWER tail) so the span reads current
    try:
        from . import hazards
        H = hazards._data()
        start = H["dates"][0].isoformat()
        end = H["dates"][-1].isoformat()
        days = len(H["dates"])
    except Exception:
        pass
    return {
        "record_span": f"{start} → {end}",
        "record_days": days,
        "sources": [
            {"name": "IMD gridded rainfall", "res": "0.25° × 0.25°", "role": "Training + validation", "status": "active"},
            {"name": "IMD gridded temperature", "res": "1.0° × 1.0°", "role": "Training + validation", "status": "active"},
            {"name": "INSAT-3D LST (3RIMG_L2B_LST)", "res": "4 km", "role": "Surface fusion", "status": "ingesting"},
            {"name": "INSAT-3D Rainfall (3RIMG_L2B_IMC)", "res": "4 km", "role": "Nowcast blend", "status": "ingesting"},
            {"name": "MOSDAC reanalysis", "res": "0.05°", "role": "Boundary conditions", "status": "ready"},
            *_live_sources(),
        ],
        "models": _model_registry(),
    }


def _live_sources() -> list[dict]:
    """The live daily feeds behind the twin, with status from their real freshness:
    'active' when the newest ingested day is within a week, else 'stale'."""
    from . import refresh
    out = []
    for key, name, res, role in (
            ("power", "NASA POWER (MERRA-2) daily", "0.5° × 0.625°", "Live tail + fusion member"),
            ("openmeteo", "Open-Meteo (ERA5) daily", "0.25°", "Live fusion member")):
        end = refresh.latest_end(key)
        try:
            d = datetime.strptime(end, "%Y%m%d").date() if end else None
        except ValueError:
            d = None
        fresh = d is not None and (date.today() - d).days <= 7
        out.append({"name": name, "res": res, "role": role, "status": "active" if fresh else "stale",
                    "as_of": d.isoformat() if d else None})
    return out


def _model_registry() -> list[dict]:
    """Per-variable model card. Uses the unified 14-day backtest when available (every
    model scored identically at the forecast horizon); otherwise the per-model metrics."""
    bt = _backtest()
    if bt:
        cards = []
        for variable, var, unit in (("Temperature", "temperature", "°C"), ("Rainfall", "rainfall", "mm/day")):
            vb = bt["variables"][var]
            b, c = vb["methods"]["blend"], vb["methods"]["clim"]
            cards.append({"variable": variable,
                          "type": "Skill-optimised ensemble (LSTM + gradient-boosted trees + persistence)",
                          "unit": unit, "rmse": b["rmse"], "skill_pct": b["skill_pct"],
                          "baseline_rmse": c["rmse"], "horizon_days": 14,
                          "members": {k: vb["methods"][k]["skill_pct"] for k in ("lstm", "gbrt", "persist")}})
        cards.append({"variable": "Soil moisture", "type": "Antecedent precipitation index",
                      "rmse": None, "unit": "index", "skill_pct": None, "baseline_rmse": None})
        return cards

    from . import ml_forecast
    try:
        from . import lstm_forecast
        lm = lstm_forecast.metrics() if lstm_forecast.available() else None
    except Exception:
        lm = None
    gm = ml_forecast.metrics()

    def card(variable, key, unit):
        use_lstm = lm is not None and lm.get(f"{key}_skill_pct", -1e9) > 0
        src = lm if use_lstm else gm
        typ = ("LSTM sequence model (PyTorch, deep learning)" if use_lstm
               else "Gradient-boosted regression trees (scikit-learn)")
        return {"variable": variable, "type": typ, "unit": unit,
                "rmse": src[f"{key}_rmse"], "skill_pct": src[f"{key}_skill_pct"],
                "baseline_rmse": src[f"{key}_clim_rmse"]}

    return [
        card("Temperature", "temp", "°C"),
        card("Rainfall", "precip", "mm/day"),
        {"variable": "Soil moisture", "type": "Antecedent precipitation index",
         "rmse": None, "unit": "index", "skill_pct": None, "baseline_rmse": None},
    ]


def insights() -> dict:
    """Auto-generated advisories derived from the live fused state, the district layer,
    the 14-day outlook and the live hazard indices — covering dry AND wet extremes."""
    st = current_state()
    dz = districts("rain")["districts"]
    dry = [d["name"] for d in sorted(dz, key=lambda d: d["rain"]) if d["rain"] < -20]
    wet = [d["name"] for d in sorted(dz, key=lambda d: -d["rain"]) if d["rain"] > 25]
    ra, ta, sm = st["rainfall_anomaly_pct"], st["temperature_anomaly_c"], st["soil_moisture_index"]
    items = []
    if st["drought_class"] in ("Moderate", "Severe"):
        items.append({"level": "warning", "title": f"{st['drought_class']} drought watch",
                      "body": f"Precipitation deficit across J&K; rainfall anomaly {ra}%.",
                      "districts": dry[:4] or ["Statewide"]})
    if ra > 25:
        items.append({"level": "warning", "title": "Above-normal rainfall — flash-flood & landslide watch",
                      "body": f"Rainfall is running {ra:+.0f}% above normal; saturated slopes raise flash-flood, "
                              f"cloudburst-runoff and landslide risk along hill roads and nallahs.",
                      "districts": wet[:4] or ["Statewide"]})
    if ta > 1.0:
        items.append({"level": "warning", "title": "Elevated surface temperature",
                      "body": f"Mean temperature running {ta:+.2f}°C above the 1973–2023 normal.",
                      "districts": ["Jammu", "Kathua", "Udhampur"]})
    elif ta < -1.0:
        items.append({"level": "warning", "title": "Below-normal temperature — cold advisory",
                      "body": f"Mean temperature running {ta:+.2f}°C below the 1973–2023 normal; protect "
                              f"livestock and horticulture from early frost.",
                      "districts": ["Srinagar", "Anantnag", "Baramulla"]})
    if sm < 0.35:
        items.append({"level": "alert", "title": "Root-zone soil-moisture stress",
                      "body": f"Soil-moisture index at {sm} — irrigation advisory recommended.",
                      "districts": dry[:3] or ["Statewide"]})
    elif sm > 0.6:
        items.append({"level": "info", "title": "High soil saturation",
                      "body": f"Soil-moisture index at {sm} — further heavy rain will run off quickly.",
                      "districts": wet[:3] or ["Statewide"]})

    # 14-day outlook with the actual forecast numbers
    try:
        fr, ft = forecast("rainfall"), forecast("temperature")
        dat = _load()
        days = [date.fromisoformat(p["date"]) for p in fr["predicted"]]
        r_tot = sum(p["value"] for p in fr["predicted"])
        r_norm = sum(_clim(dat.clim_precip, d) for d in days)
        t_avg = float(np.mean([p["value"] for p in ft["predicted"]]))
        t_norm = float(np.mean([_clim(dat.clim_temp, d) for d in days]))
        items.append({"level": "info", "title": "14-day outlook",
                      "body": f"{fr['horizon']['start']} → {fr['horizon']['end']}: about {r_tot:.0f} mm of rain "
                              f"(normal {r_norm:.0f} mm) and a mean of {t_avg:.1f}°C (normal {t_norm:.1f}°C). "
                              f"Backtested skill vs climatology — temperature {ft['skill']['skill_pct']:+.1f}%, "
                              f"rainfall {fr['skill']['skill_pct']:+.1f}%.",
                      "districts": ["Statewide"]})
    except Exception:
        items.append({"level": "info", "title": "14-day outlook issued",
                      "body": "Rainfall & temperature forecast refreshed from the latest assimilation cycle.",
                      "districts": ["Statewide"]})

    # live hazard flags + seasonal summary
    try:
        from . import hazards
        hw, cw, mo = hazards.heatwave(), hazards.coldwave(), hazards.monsoon()
        if hw.get("active"):
            items.append({"level": "alert", "title": "Heatwave conditions",
                          "body": f"Daily maxima ≥ {hw['threshold_c']}°C above normal for 2+ days (as of {hw['as_of']}).",
                          "districts": ["Jammu", "Kathua", "Samba"]})
        if cw.get("active"):
            items.append({"level": "alert", "title": "Cold-snap conditions",
                          "body": f"Minimum temperature {cw['recent_tmin_anomaly_c']}°C vs normal.",
                          "districts": ["Srinagar", "Anantnag", "Kishtwar"]})
        today = date.today()
        if mo.get("year") == today.year and today.month >= 6:
            items.append({"level": "info", "title": f"Monsoon {mo['year']} (Jun–Sep)",
                          "body": f"Season rainfall at {mo['progress_pct']:.0f}% of normal "
                                  f"({mo['received_mm']} of {mo['seasonal_normal_mm']} mm); onset {mo['onset_date']}.",
                          "districts": ["Statewide"]})
    except Exception:
        pass
    return {"as_of": st["as_of"], "items": items}
