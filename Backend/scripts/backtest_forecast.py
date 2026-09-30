"""Unified 14-day forecast backtest + skill-optimised blending.

Scores every forecaster the SAME way — RMSE over leads 1–14 on held-out issue dates —
so model choice is apples-to-apples (the GBRT was previously scored 1-day-ahead and the
LSTM over 14 days, which are not comparable).

Methods (per variable):
  clim     day-of-year climatology
  persist  climatology + damped persistence of the last-5-day anomaly (0.7^lead)
  gbrt     gradient-boosted trees, recursive 14-step
  lstm     PyTorch LSTM, direct 14-step
  app      the previous hard-coded ensemble (0.6 × chosen ML + 0.4 × persist)
  blend    per-lead non-negative weights over {gbrt, lstm, persist} anomalies, FIT on the
           2021 issue dates and SCORED on 2022–2023 (both models are trained on ≤2020,
           so neither the fit nor the score touches their training data)

Usage (from Backend/):  python scripts/backtest_forecast.py
Writes models/forecast_backtest.json, which the forecast API uses for its ensemble
weights and its honest 14-day skill numbers.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import numpy as np
from scipy.optimize import nnls

from app.services import lstm_forecast, ml_forecast
from app.services.climate import _load

OUT = BASE / "models" / "forecast_backtest.json"
H = 14


def main():
    t0 = time.time()
    dat = _load()
    n = len(dat.dates)
    split = int(dat.year.max()) - 3                      # models are trained on <= split
    val_year = split + 1
    origins = [a for a in range(60, n - H) if dat.year[a] > split]
    print(f"[backtest] {len(origins)} issue dates, val year {val_year}, test {val_year + 1}–{dat.year.max()}", flush=True)
    # Warming trend fit ONLY on the models' training years (no leakage into 2021–2023):
    # the 1973–2023 climatology is centred ~1998, so present-day temperatures sit above it.
    yrs = np.array(sorted({int(y) for y in dat.year if y <= split}))
    full = [y for y in yrs if (dat.year == y).sum() >= 330]
    ann = np.array([dat.temp[dat.year == y].mean() for y in full])
    slope = float(np.polyfit(full, ann, 1)[0])
    mid = float(np.mean(dat.year[dat.year <= split]))
    out = {"horizon_days": H, "val_year": int(val_year),
           "test_period": f"{val_year + 1}–{int(dat.year.max())}",
           "temp_trend_c_per_year": round(slope, 5), "trend_mid_year": round(mid, 2),
           "variables": {}}

    for var, is_temp in (("temperature", True), ("rainfall", False)):
        obs = dat.temp if is_temp else dat.precip
        clim = dat.clim_temp if is_temp else dat.clim_precip
        T = np.zeros((len(origins), H)); C = np.zeros_like(T); P = np.zeros_like(T)
        G = np.zeros_like(T); L = np.zeros_like(T); CT = np.zeros_like(T)
        for r, a in enumerate(origins):
            doys = dat.doy[a + 1:a + H + 1]
            T[r] = obs[a + 1:a + H + 1]
            C[r] = clim[doys]
            # trend-adjusted climatology for temperature (plain climatology for rainfall)
            CT[r] = C[r] + (slope * (dat.dates[a].year - mid) if is_temp else 0.0)
            last_anom = float(obs[a - 4:a + 1].mean() - CT[r, 0] + C[r, 0]
                              - clim[dat.doy[a - 4:a + 1]].mean())
            P[r] = CT[r] + last_anom * (0.7 ** np.arange(1, H + 1))
            G[r] = ml_forecast.forecast_series(var, H, anchor_index=a)
            L[r] = lstm_forecast.forecast_series(var, H, anchor_index=a)
            if r % 200 == 0:
                print(f"  [{var}] {r}/{len(origins)} ({time.time()-t0:.0f}s)", flush=True)

        chosen = L if is_temp else G                         # the previous app gating
        APP = 0.6 * chosen + 0.4 * P
        if not is_temp:
            P, APP = np.clip(P, 0, None), np.clip(APP, 0, None)

        yr = np.array([dat.year[a] for a in origins])
        val, test = yr == val_year, yr > val_year

        # per-lead NNLS blend on anomalies relative to the (trend-adjusted) climatology,
        # weights fit on the validation year only
        W = np.zeros((H, 3))
        B = np.zeros_like(T)
        for h in range(H):
            Xv = np.stack([G[val, h] - CT[val, h], L[val, h] - CT[val, h], P[val, h] - CT[val, h]], 1)
            yv = T[val, h] - CT[val, h]
            w, _ = nnls(Xv, yv)
            W[h] = w
            B[:, h] = CT[:, h] + np.stack([G[:, h] - CT[:, h], L[:, h] - CT[:, h], P[:, h] - CT[:, h]], 1) @ w
        if not is_temp:
            B = np.clip(B, 0, None)

        def rmse(M, mask):
            return float(np.sqrt(np.mean((M[mask] - T[mask]) ** 2)))

        methods = {"clim": C, "clim_trend": CT, "persist": P, "gbrt": G, "lstm": L, "app": APP, "blend": B}
        rc = rmse(C, test)
        res = {}
        for k, M in methods.items():
            r = rmse(M, test)
            res[k] = {"rmse": round(r, 3), "skill_pct": round((1 - r / rc) * 100, 1),
                      "mae": round(float(np.mean(np.abs(M[test] - T[test]))), 3),
                      "rmse_by_lead": [round(float(np.sqrt(np.mean((M[test, h] - T[test, h]) ** 2))), 3)
                                       for h in range(H)]}
        best = min(res, key=lambda k: res[k]["rmse"])
        resid = float(np.std((B - T)[test]))
        out["variables"][var] = {
            "methods": res, "best": best,
            "blend_weights": [[round(float(x), 4) for x in W[h]] for h in range(H)],
            "blend_members": ["gbrt", "lstm", "persist"],
            "blend_resid_std": round(resid, 3),
            "n_val": int(val.sum()), "n_test": int(test.sum()),
        }
        print(f"\n[{var}] 14-day RMSE on {int(test.sum())} test issue dates (skill vs climatology):", flush=True)
        for k in methods:
            print(f"   {k:8s} rmse {res[k]['rmse']:.3f}   skill {res[k]['skill_pct']:+.1f}%", flush=True)
        print(f"   best = {best}", flush=True)

    out["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n[done] {OUT} ({time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
