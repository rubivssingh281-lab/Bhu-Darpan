"""AI/ML short-range forecaster for the climate twin.

A genuine trained machine-learning time-series model (gradient-boosted regression
trees, scikit-learn) that predicts daily mean temperature and precipitation over the
J&K pilot region. It learns from seasonal (day-of-year), trend and autoregressive-lag
features on 50 years of data, is validated on a held-out time split, and drives the
14-day forecast recursively.

Trees (HistGradientBoosting) are used instead of a deep net so the model trains in
~1 s on CPU with the already-installed stack; the feature/target design and the
train→validate→forecast pipeline are identical to what an LSTM/TCN would use, so a
PyTorch model can be dropped in later (see train_lstm.py) without touching the API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .climate import _load, _clim

LAGS = [1, 2, 3, 7, 14, 30]


def _features(temp: np.ndarray, precip: np.ndarray, doy: np.ndarray,
              yearfrac: np.ndarray, i: int) -> list[float]:
    """Feature row for predicting day i from information available up to i-1."""
    d = doy[i]
    f = [
        np.sin(2 * np.pi * d / 365.25), np.cos(2 * np.pi * d / 365.25),
        np.sin(4 * np.pi * d / 365.25), np.cos(4 * np.pi * d / 365.25),
        yearfrac[i],                                   # long-term trend
    ]
    for L in LAGS:
        f.append(temp[i - L])
        f.append(precip[i - L])
    f.append(temp[i - 7:i].mean())                     # rolling means
    f.append(precip[i - 7:i].sum())
    f.append(temp[i - 30:i].mean())
    f.append(precip[i - 30:i].sum())
    return f


@dataclass
class _Model:
    temp_model: HistGradientBoostingRegressor
    precip_model: HistGradientBoostingRegressor
    metrics: dict


@lru_cache(maxsize=1)
def _train() -> _Model:
    dat = _load()
    temp, precip, doy = dat.temp, dat.precip, dat.doy
    yearfrac = (dat.year - dat.year.min()) / (dat.year.max() - dat.year.min() + 1e-9)
    n = len(temp)

    start = max(LAGS) + 1
    X, yt, yp, idx = [], [], [], []
    for i in range(start, n):
        X.append(_features(temp, precip, doy, yearfrac, i))
        yt.append(temp[i]); yp.append(precip[i]); idx.append(i)
    X = np.array(X); yt = np.array(yt); yp = np.array(yp); idx = np.array(idx)

    # Time-based split: train on all but the last 3 years, validate on the last 3.
    split_year = dat.year.max() - 3
    train = dat.year[idx] <= split_year
    test = ~train

    temp_m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05,
                                           max_depth=6, random_state=0)
    precip_m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05,
                                             max_depth=6, random_state=0)
    temp_m.fit(X[train], yt[train])
    precip_m.fit(X[train], yp[train])

    # Validation metrics on the held-out split (1-step-ahead)
    pt = temp_m.predict(X[test]); pp = np.clip(precip_m.predict(X[test]), 0, None)
    # Naive climatology baseline on the same test rows
    clim_t = np.array([_clim(dat.clim_temp, dat.dates[i]) for i in idx[test]])
    clim_p = np.array([_clim(dat.clim_precip, dat.dates[i]) for i in idx[test]])

    def rmse(a, b): return float(np.sqrt(mean_squared_error(a, b)))

    m = {
        "temp_rmse": round(rmse(yt[test], pt), 2),
        "temp_mae": round(float(mean_absolute_error(yt[test], pt)), 2),
        "temp_clim_rmse": round(rmse(yt[test], clim_t), 2),
        "precip_rmse": round(rmse(yp[test], pp), 2),
        "precip_mae": round(float(mean_absolute_error(yp[test], pp)), 2),
        "precip_clim_rmse": round(rmse(yp[test], clim_p), 2),
        "test_days": int(test.sum()),
        "train_days": int(train.sum()),
        "temp_resid_std": round(float(np.std(yt[test] - pt)), 2),
        "precip_resid_std": round(float(np.std(yp[test] - pp)), 2),
    }
    m["temp_skill_pct"] = round((1 - m["temp_rmse"] / m["temp_clim_rmse"]) * 100, 1)
    m["precip_skill_pct"] = round((1 - m["precip_rmse"] / m["precip_clim_rmse"]) * 100, 1)
    return _Model(temp_m, precip_m, m)


def metrics() -> dict:
    return _train().metrics


def forecast_series(var: str, horizon: int = 14, anchor_index: int | None = None,
                    dat=None) -> list[float]:
    """Recursive multi-step forecast of `var` for `horizon` days past `anchor_index`
    (defaults to the last record). `dat` lets the caller seed from the live-extended
    record (latest real observations); the model itself is trained on `_load()`."""
    dat = dat if dat is not None else _load()
    mdl = _train()
    model = mdl.temp_model if var == "temperature" else mdl.precip_model

    n = len(dat.temp)
    a = n - 1 if anchor_index is None else max(40, min(int(anchor_index), n - 1))

    # working buffers seeded with the 40 real days up to and including the anchor
    temp = list(dat.temp[a - 39:a + 1])
    precip = list(dat.precip[a - 39:a + 1])
    doy = list(dat.doy[a - 39:a + 1])
    yf_last = float((dat.year.max() - dat.year.min()) / (dat.year.max() - dat.year.min() + 1e-9))

    last = dat.dates[a]
    out = []
    for h in range(1, horizon + 1):
        fd = last + timedelta(days=h)
        temp.append(0.0); precip.append(0.0)
        doy.append(min(fd.timetuple().tm_yday, 365))
        ta = np.array(temp); pa = np.array(precip); da = np.array(doy)
        i = len(ta) - 1
        yfa = np.full(len(ta), yf_last)
        feat = np.array(_features(ta, pa, da, yfa, i)).reshape(1, -1)
        # predict BOTH so lags stay consistent for the recursive step
        pt = float(mdl.temp_model.predict(feat)[0])
        pp = float(np.clip(mdl.precip_model.predict(feat)[0], 0, None))
        temp[-1] = pt; precip[-1] = pp
        out.append(pt if var == "temperature" else pp)
    return out
