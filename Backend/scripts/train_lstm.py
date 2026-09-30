"""Train the PyTorch LSTM climate forecaster (temperature + rainfall).

Deep-learning forecaster for the digital twin: a 30-day → 14-day sequence model that
learns the day-of-year *anomaly* of mean temperature and rainfall over the J&K pilot
region, validated on a held-out time split against a climatology baseline.

Usage (from Backend/, venv active):
    python scripts/train_lstm.py                 # ~1-2 min on CPU
    python scripts/train_lstm.py --epochs 40

Writes:
    models/lstm_climate.pt     - weights for both variables (+ arch/normalisation)
    models/lstm_metrics.json   - held-out RMSE / MAE / skill vs climatology

The forecast API auto-uses these weights via app/services/lstm_forecast.py; if they
are absent it falls back to the scikit-learn gradient-boosted forecaster.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # Backend/
sys.path.insert(0, str(BASE))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from app.services.climate import _load
from app.services.lstm_forecast import WINDOW, HORIZON, HIDDEN, build_model

WEIGHTS = BASE / "models" / "lstm_climate.pt"
METRICS = BASE / "models" / "lstm_metrics.json"
SEED = 42


def build_windows(obs, clim, doy, year):
    """Return X (N,WINDOW,3 z-anom+season), Yz (N,HORIZON z-anom), and per-window
    target climatology / actual / issue-year for reconstruction & splitting."""
    anom = obs - clim[doy]
    sd = float(anom.std() + 1e-6)
    z = anom / sd
    sin = np.sin(2 * np.pi * doy / 365.25)
    cos = np.cos(2 * np.pi * doy / 365.25)
    n = len(obs)
    X, Yz, tgt_clim, tgt_act, issue_year = [], [], [], [], []
    for i in range(WINDOW, n - HORIZON):
        X.append(np.stack([z[i - WINDOW:i], sin[i - WINDOW:i], cos[i - WINDOW:i]], axis=1))
        Yz.append(z[i:i + HORIZON])
        tgt_clim.append(clim[doy[i:i + HORIZON]])
        tgt_act.append(obs[i:i + HORIZON])
        issue_year.append(year[i])
    return (np.asarray(X, np.float32), np.asarray(Yz, np.float32),
            np.asarray(tgt_clim, np.float32), np.asarray(tgt_act, np.float32),
            np.asarray(issue_year), sd)


def train_one(var, obs, clim, doy, year, epochs, is_temp):
    X, Yz, tgt_clim, tgt_act, iyear, sd = build_windows(obs, clim, doy, year)
    split_year = year.max() - 3
    tr, te = iyear <= split_year, iyear > split_year

    torch.manual_seed(SEED)
    model = build_model(HIDDEN, HORIZON)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    crit = nn.MSELoss()
    dl = DataLoader(TensorDataset(torch.from_numpy(X[tr]), torch.from_numpy(Yz[tr])),
                    batch_size=128, shuffle=True)

    for ep in range(1, epochs + 1):
        model.train()
        for xb, yb in dl:
            opt.zero_grad()
            loss = crit(model(xb), yb)
            loss.backward()
            opt.step()

    # ---- evaluate on the held-out split, reconstructing real values ----
    model.eval()
    with torch.no_grad():
        pred_z = model(torch.from_numpy(X[te])).numpy()          # (Nte, HORIZON)
    pred = tgt_clim[te] + pred_z * sd
    if not is_temp:
        pred = np.clip(pred, 0, None)
    actual = tgt_act[te]
    clim_pred = tgt_clim[te]

    def rmse(a, b): return float(np.sqrt(np.mean((a - b) ** 2)))
    def mae(a, b): return float(np.mean(np.abs(a - b)))

    r_model = rmse(pred, actual)
    r_clim = rmse(clim_pred, actual)
    resid_std = float(np.std(actual - pred))
    print(f"[{var}] test windows={te.sum()}  RMSE={r_model:.3f}  clim={r_clim:.3f}  "
          f"skill={(1 - r_model / r_clim) * 100:.1f}%")

    stats = {
        f"{'temp' if is_temp else 'precip'}_rmse": round(r_model, 2),
        f"{'temp' if is_temp else 'precip'}_mae": round(mae(pred, actual), 2),
        f"{'temp' if is_temp else 'precip'}_clim_rmse": round(r_clim, 2),
        f"{'temp' if is_temp else 'precip'}_skill_pct": round((1 - r_model / r_clim) * 100, 1),
        f"{'temp' if is_temp else 'precip'}_resid_std": round(resid_std, 2),
    }
    return model, sd, stats, int(tr.sum()), int(te.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=35)
    args = ap.parse_args()
    t0 = time.time()

    dat = _load()
    doy, year = dat.doy, dat.year
    print(f"[data] {len(dat.dates)} daily records, window={WINDOW} -> horizon={HORIZON}")

    tm, tsd, tmet, ntr, nte = train_one("temperature", dat.temp, dat.clim_temp, doy, year, args.epochs, True)
    pm, psd, pmet, _, _ = train_one("rainfall", dat.precip, dat.clim_precip, doy, year, args.epochs, False)

    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "temperature": {"state_dict": tm.state_dict(), "sd": tsd},
        "rainfall": {"state_dict": pm.state_dict(), "sd": psd},
        "hidden": HIDDEN, "horizon": HORIZON, "window": WINDOW,
    }, WEIGHTS)

    metrics = {"model": "LSTM (PyTorch, 30d→14d sequence, anomaly target)",
               "train_days": ntr, "test_days": nte,
               "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"), **tmet, **pmet}
    METRICS.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("\n================  LSTM RESULTS  ================")
    print(f"  temperature: RMSE {tmet['temp_rmse']}  skill {tmet['temp_skill_pct']}% vs climatology")
    print(f"  rainfall:    RMSE {pmet['precip_rmse']}  skill {pmet['precip_skill_pct']}% vs climatology")
    print(f"  weights -> {WEIGHTS}")
    print(f"  metrics -> {METRICS}")
    print(f"  total time: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
