# Climate Data Ingestion Pipeline

Bhū-Darpan combines observational satellite imagery with gridded national climate data.

## Gridded Sources

| Dataset | Provider | Resolution | Primary Variables |
|---|---|---|---|
| **NASA POWER** | NASA Langley (MERRA-2) | 0.5° × 0.5° | T2M, PRECTOTCORR, RH2M |
| **IMD Gridded** | India Meteorological Dept | 0.25° × 0.25° | Daily Rainfall & Surface Temp |
| **Open-Meteo** | ECMWF / ERA5 | Hourly / 0.1° | Real-time weather feeds |

## Regridding & Fusion
- Gridded feeds are regridded onto a unified **0.25° coordinate mesh** covering Jammu & Kashmir (`32.0°N–37.0°N`, `73.0°E–80.5°E`).
- Anomaly baselines are computed relative to a multi-decade climatology baseline.
