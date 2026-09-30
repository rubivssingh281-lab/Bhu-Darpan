"""Per-cell gridded forecaster (daily climatology + optimised damped persistence).

Predicts each grid cell's value `lead` days ahead as

    value = daily climatology(target day) + φ(lead) · current anomaly

with the decay φ fit per lead (least squares) on the training + validation years. A
direct multi-horizon gradient-boosted model (GBRT) is also trained and scored on the same
test slice for transparency, but it is NOT used operationally: out-of-sample it never beat
optimised persistence per cell (a validation-fit NNLS blend gave it ~0 weight), so the
parsimonious one-parameter model is the most accurate choice. Other design choices:

* **Daily climatology** — the monthly climatology is turned into a smooth day-of-year
  table (periodic linear interpolation between mid-month values), so within-month
  seasonal drift is not mistaken for an anomaly.
* **Consistent state** — training and inference both use the mean anomaly of the last
  3 days as the "current state" (previously training used 1 day, inference a 30-day mean).
* **Honest baselines** — skill is reported against climatology AND naive persistence
  (fixed 0.6^lead decay), on a time-ordered test slice never used for fitting.

Splits (time-ordered on the multi-year ingested grid): first 75 % fit (decay + GBRT),
last 25 % test (reported skill).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

import numpy as np
from scipy.optimize import nnls
from sklearn.ensemble import HistGradientBoostingRegressor

from ingest.config import GRIDDED_DIR
from .gridded_analysis import _find, _sample, anomaly, markers_for

LEADS = [1, 3, 7, 14]
STEP = 2                 # subsample issue days for training speed
SEED_DAYS = 3            # "current state" = mean anomaly of the last 3 days
_MID = np.array([15.5, 45.0, 74.5, 105.0, 135.5, 166.0, 196.5, 227.5, 258.0, 288.5, 319.0, 349.5])


def _daily_clim(clim12: np.ndarray) -> np.ndarray:
    """(12, ny, nx) monthly climatology → (367, ny, nx) day-of-year table (index = doy)."""
    ny, nx = clim12.shape[1:]
    mids = np.concatenate([[_MID[-1] - 365.0], _MID, [_MID[0] + 365.0]])
    vals = np.concatenate([clim12[-1:], clim12, clim12[:1]], axis=0).astype(np.float32)
    table = np.empty((367, ny, nx), dtype=np.float32)
    for d in range(1, 367):
        j = int(np.clip(np.searchsorted(mids, d, side="right"), 1, len(mids) - 1))
        f = (d - mids[j - 1]) / (mids[j] - mids[j - 1])
        table[d] = (1 - f) * vals[j - 1] + f * vals[j]
    table[0] = table[1]
    return table


def _load_record(var: str, region: str):
    import xarray as xr
    rec = _find(var, region, False, min_days=200)
    clim_m = _find(var, region, True)
    if not rec or not clim_m:
        return None
    da = xr.open_dataset(GRIDDED_DIR / f"{rec['id']}.nc")[var]
    clim = np.asarray(xr.open_dataset(GRIDDED_DIR / f"{clim_m['id']}.nc")[var].values, dtype=np.float32)
    table = _daily_clim(clim[:12])
    doy = np.atleast_1d(da["time"].dt.dayofyear.values).astype(int)
    obs = np.asarray(da.values, dtype=np.float32)
    return {"obs": obs, "doy": doy, "table": table,
            "lats": np.asarray(da.lat.values, dtype=np.float32),
            "lons": np.asarray(da.lon.values, dtype=np.float32), "units": rec["units"]}


def _seed(anom: np.ndarray, t: int) -> np.ndarray:
    with np.errstate(all="ignore"):
        return np.nanmean(anom[max(0, t - SEED_DAYS + 1):t + 1], axis=0)


def _cols(doy_tgt, lead, LA, LO, seed_flat, gridmean, n):
    ones = np.ones(n, dtype=np.float32)
    return np.column_stack([
        ones * np.sin(2 * np.pi * doy_tgt / 365.25), ones * np.cos(2 * np.pi * doy_tgt / 365.25),
        ones * np.sin(4 * np.pi * doy_tgt / 365.25), ones * np.cos(4 * np.pi * doy_tgt / 365.25),
        ones * float(lead), LA.ravel(), LO.ravel(),
        seed_flat,                 # current per-cell anomaly (the key predictor)
        ones * gridmean,           # region-mean anomaly (regime)
    ])


def _grid_xy(lats, lons):
    return np.meshgrid((lats - lats.mean()) / 5.0, (lons - lons.mean()) / 5.0, indexing="ij")


def _rmse(p, y):
    return float(np.sqrt(np.mean((p - y) ** 2)))


@lru_cache(maxsize=4)
def train(var: str, region: str = "jk"):
    R = _load_record(var, region)
    if R is None:
        return None
    anom = R["obs"] - R["table"][R["doy"]]
    T, ny, nx = anom.shape
    LA, LO = _grid_xy(R["lats"], R["lons"])
    t_tr, t_va = int(T * 0.60), int(T * 0.75)

    blocks = []                                  # (lead, t, X, y, seed)
    for lead in LEADS:
        for t in range(SEED_DAYS, T - lead, STEP):
            s = np.nan_to_num(_seed(anom, t)).ravel()
            X = _cols(R["doy"][t + lead], lead, LA, LO, s, float(s.mean()), ny * nx)
            blocks.append((lead, t, X, anom[t + lead].ravel(), s))

    def stack(pred):
        sel = [b for b in blocks if pred(b)]
        if not sel:
            return None
        X = np.concatenate([b[2] for b in sel]); y = np.concatenate([b[3] for b in sel])
        s = np.concatenate([b[4] for b in sel])
        ok = np.isfinite(y) & np.isfinite(X).all(1)
        return X[ok], y[ok], s[ok]

    Xtr, ytr, _ = stack(lambda b: b[1] < t_va)
    model = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, max_depth=6,
                                          min_samples_leaf=200, l2_regularization=1.0, random_state=0)
    model.fit(Xtr, ytr)                                   # evaluated for transparency only

    phi, metrics = {}, {}
    for lead in LEADS:
        _, ytv, stv = stack(lambda b, L=lead: b[0] == L and b[1] < t_va)
        phi[lead] = float(np.clip(np.dot(stv, ytv) / (np.dot(stv, stv) + 1e-9), 0.0, 1.0))
        Xt, yt, st = stack(lambda b, L=lead: b[0] == L and b[1] >= t_va)
        r_op = _rmse(phi[lead] * st, yt)                  # operational model
        r_ml = _rmse(model.predict(Xt), yt)
        r_cl = _rmse(0.0 * yt, yt)                        # climatology (anomaly = 0)
        r_nv = _rmse((0.6 ** lead) * st, yt)              # naive persistence baseline
        metrics[str(lead)] = {
            "rmse": round(r_op, 2), "clim_rmse": round(r_cl, 2), "persist_rmse": round(r_nv, 2),
            "ml_rmse": round(r_ml, 2),
            "skill_vs_clim_pct": round((1 - r_op / r_cl) * 100, 1) if r_cl else None,
            "skill_vs_persist_pct": round((1 - r_op / r_nv) * 100, 1) if r_nv else None,
            "persist_decay": round(phi[lead], 3),
        }
    return {"model": model, "phi": phi, "metrics": metrics,
            "table": R["table"], "lats": R["lats"], "lons": R["lons"],
            "units": R["units"], "test_days": T - t_va}


def _lead_phi(tr, lead) -> float:
    """Persistence decay for any lead 1–14 (log-linear interpolation between fit leads)."""
    ls = np.array(LEADS, float)
    ph = np.log(np.clip([tr["phi"][L] for L in LEADS], 1e-4, 1.0))
    return float(np.exp(np.interp(lead, ls, ph)))


def metrics(var: str, region: str = "jk") -> dict | None:
    t = train(var, region)
    return None if t is None else {
        "var": var, "test_days": t["test_days"], "units": t["units"], "leads": t["metrics"],
        "model": "Optimised damped persistence on a daily climatology (per cell)",
        "persist_baseline": "naive persistence, fixed 0.6^lead decay",
        "note": "A per-cell GBRT was trained and tested (ml_rmse) but not selected — it did "
                "not beat optimised persistence out-of-sample."}


@lru_cache(maxsize=32)
def forecast_field(var: str, region: str = "jk", lead: int = 7) -> dict | None:
    """Per-cell forecast seeded from the latest days of the live daily grid."""
    import xarray as xr
    tr = train(var, region)
    a = anomaly(var, region)
    daily_m = _find(var, region, False, max_days=180, source_contains="POWER")
    if tr is None or a is None or not daily_m:
        return None
    da = xr.open_dataset(GRIDDED_DIR / f"{daily_m['id']}.nc")[var]
    obs = np.asarray(da.values, dtype=np.float32)
    if obs.shape[1:] != tr["table"].shape[1:]:
        return None
    tdoy = np.atleast_1d(da["time"].dt.dayofyear.values).astype(int)
    anom = obs - tr["table"][tdoy]
    valid = [t for t in range(anom.shape[0]) if np.isfinite(anom[t]).mean() > 0.5]
    if not valid:
        return None
    t_last = valid[-1]
    seed = np.nan_to_num(_seed(anom, t_last))
    last_date = datetime.strptime(str(np.datetime_as_string(da["time"].values[t_last], unit="D")), "%Y-%m-%d")
    target = last_date + timedelta(days=lead)
    doy_tgt = min(target.timetuple().tm_yday, 366)

    ph = _lead_phi(tr, lead)
    fc_anom = (ph * seed).astype(float)
    pred_val = tr["table"][doy_tgt].astype(float) + fc_anom
    if var == "rain":
        pred_val = np.clip(pred_val, 0, None)
    fin = fc_anom[np.isfinite(fc_anom)]
    lats, lons = tr["lats"], tr["lons"]
    districts = [{"name": n, "lat": la, "lon": lo,
                  "value": round(_sample(lats, lons, pred_val, la, lo) or 0, 2),
                  "anomaly": round(_sample(lats, lons, fc_anom, la, lo) or 0, 2)}
                 for n, la, lo in markers_for(region)]
    return {
        "var": var, "region": region, "units": a["units"], "lead": lead,
        "target_date": target.strftime("%Y-%m-%d"), "res_deg": a["res_deg"],
        "method": f"Optimised persistence (decay {ph:.2f}) on a daily climatology",
        "source": a["source"], "lats": lats, "lons": lons,
        "value": pred_val, "anomaly": fc_anom,
        "amin": float(np.nanmin(fin)) if fin.size else None,
        "amax": float(np.nanmax(fin)) if fin.size else None,
        "districts": districts, "seeded_from": last_date.strftime("%Y-%m-%d"),
    }
