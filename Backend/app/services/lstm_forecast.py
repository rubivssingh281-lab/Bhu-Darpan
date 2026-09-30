"""Deep-learning climate forecaster — a PyTorch LSTM for the twin.

A trained sequence model that predicts the next 14 days of mean **temperature** and
**rainfall** over the J&K pilot region from a 30-day window. It learns the *anomaly*
(value − day-of-year climatology), which is what lets it beat a climatology baseline;
at inference the predicted anomaly is added back to the climatology of each target day.

Exposes the same interface as the scikit-learn forecaster (`metrics()`,
`forecast_series(var, horizon)`, `available()`) so it drops straight into the forecast
API. Torch is optional: if it or the weights are missing, `available()` is False and
the app falls back to the gradient-boosted forecaster.
"""
from __future__ import annotations

import json
from datetime import timedelta
from functools import lru_cache

import numpy as np

from ..config import settings
from .climate import _load

try:
    import torch
    import torch.nn as nn
    _TORCH = True
except Exception:  # pragma: no cover
    _TORCH = False

WINDOW = 30
HORIZON = 14
HIDDEN = 48

WEIGHTS = settings.base_dir / "models" / "lstm_climate.pt"
METRICS_PATH = settings.base_dir / "models" / "lstm_metrics.json"


def build_model(hidden: int = HIDDEN, horizon: int = HORIZON):
    """LSTM(3 features -> hidden) -> Linear(horizon). Same arch for train & inference."""
    if not _TORCH:
        raise RuntimeError("PyTorch is not installed")

    class ClimateLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(3, hidden, num_layers=1, batch_first=True)
            self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, horizon))

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1])

    return ClimateLSTM()


@lru_cache(maxsize=1)
def _load_models():
    """Return {'temperature': (model, sd), 'rainfall': (model, sd)} or None."""
    if not _TORCH or not WEIGHTS.exists():
        return None
    ckpt = torch.load(WEIGHTS, map_location="cpu")
    out = {}
    for var in ("temperature", "rainfall"):
        m = build_model(ckpt.get("hidden", HIDDEN), ckpt.get("horizon", HORIZON))
        m.load_state_dict(ckpt[var]["state_dict"])
        m.eval()
        out[var] = (m, float(ckpt[var]["sd"]))
    return out


def available() -> bool:
    return _load_models() is not None


@lru_cache(maxsize=1)
def metrics() -> dict | None:
    if METRICS_PATH.exists():
        try:
            return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def _window_features(dat, clim, sd, end: int | None = None):
    """WINDOW days ending at `end` (default last) as (1, WINDOW, 3):
    [anomaly_z, sin(doy), cos(doy)]."""
    n = len(dat.dates)
    e = n - 1 if end is None else int(end)
    idx = np.arange(e - WINDOW + 1, e + 1)
    doy = dat.doy[idx]
    obs = (dat.temp if clim is dat.clim_temp else dat.precip)[idx]
    anom = obs - clim[doy]
    z = anom / sd
    feat = np.stack([z,
                     np.sin(2 * np.pi * doy / 365.25),
                     np.cos(2 * np.pi * doy / 365.25)], axis=1).astype(np.float32)
    return feat[None, ...]


def forecast_series(var: str, horizon: int = HORIZON, anchor_index: int | None = None,
                    dat=None) -> list[float]:
    """Predict `horizon` (<=14) days past `anchor_index` (default last record) for `var`
    ('temperature' | 'rainfall'). `dat` lets the caller seed from the live-extended record
    so the 30-day input window is the latest real observations."""
    models = _load_models()
    dat = dat if dat is not None else _load()
    is_temp = var == "temperature"
    clim = dat.clim_temp if is_temp else dat.clim_precip
    model, sd = models[var]

    n = len(dat.dates)
    a = n - 1 if anchor_index is None else max(WINDOW, min(int(anchor_index), n - 1))
    feat = _window_features(dat, clim, sd, end=a)
    with torch.no_grad():
        pred_z = model(torch.from_numpy(feat)).numpy()[0]      # (HORIZON,)

    last = dat.dates[a]
    out = []
    for h in range(1, min(horizon, HORIZON) + 1):
        fd = last + timedelta(days=h)
        d = min(fd.timetuple().tm_yday, 365)
        val = float(clim[d] + pred_z[h - 1] * sd)
        out.append(val if is_temp else max(0.0, val))
    return out
