# Bhū-Darpan — Complete Project Guide & Judge FAQ

> **भू-दर्पण (Bhū-Darpan) = "Earth-Mirror"** — an AI-powered **Climate Digital Twin**
> for Jammu & Kashmir, bundled with a **satellite image-intelligence** module for
> land-cover mapping, change detection, and drought/flood/fire disaster alerting.
>
> This single document is the team's study guide **and** the judge-FAQ crib sheet.
> Every component below has a 2+ line explanation you can read out loud in a Q&A.

---

## 0. How to use this document

- **Team members:** read Section 1–3 for the big picture, then jump to *your* area in
  Section 10 (Team Roles). Read the 2-line blurbs for anything you might be asked about.
- **Before judging:** skim Section 11 (Judge FAQ). Each answer is written the way you'd
  say it out loud.
- **Everything here is real and running** — no mock data, no placeholder features. If a
  number appears (e.g. "98.33% accuracy"), it comes from a metrics file in the repo.

---

## 1. What is Bhū-Darpan? (the elevator pitch)

Bhū-Darpan is a **digital twin of the J&K climate system**: a continuously-updated,
data-driven mirror of the real region that fuses national satellite and ground datasets,
runs AI forecasts on top, and turns the result into decision-ready advisories.

It has **two integrated halves**, served from one application:
1. **Climate Digital Twin** (`/`) — live regional state, 14-day AI forecasts, hazard
   analytics, a what-if scenario simulator, multi-source data assimilation, and advisories.
2. **Satellite Image Intelligence** (`/satellite`) — upload a satellite/aerial image and
   get land-cover segmentation, object detection, change detection, and disaster
   detection with an automated authority-alert report.

**Why it matters:** J&K faces droughts, flash floods, cloudbursts, avalanches and
forest fires. Officials today read these signals from many disconnected portals.
Bhū-Darpan fuses them into one live, explainable picture and forecasts what happens next.

---

## 2. The problem → our solution (5-step story)

1. **Problem:** climate risk data for J&K is fragmented across IMD, ISRO/MOSDAC, and
   global reanalyses, and none of it forecasts or fuses automatically.
2. **Collect:** we ingest real gridded datasets (NASA POWER, Open-Meteo/ERA5, IMD-style,
   INSAT) as NetCDF and regrid them to a common 0.25° grid.
3. **Fuse:** two independent reanalyses are merged with optimal interpolation, and the
   fused field is validated against the IMD station record.
4. **Model:** deep-learning + gradient-boosted forecasters predict the next 14 days, and
   a CNN classifies land cover from imagery — every model is skill-gated against a
   climatology baseline so we never show a forecast worse than "the seasonal average."
5. **Act:** the twin outputs live anomalies, hazard indices, scenario simulations, and
   auto-generated advisories/alerts that a decision-maker can act on.

---

## 3. System architecture (one paragraph)

A single **FastAPI** (Python 3.12) backend serves everything: it exposes ~40 REST
endpoints, runs the AI models on CPU, ingests and caches gridded climate data, and
serves the two web UIs directly as static single-page apps. Data persists in a local
**SQLite** file through a tiny Mongo-style interface, so there is no external database to
run. The frontend is dependency-free vanilla JavaScript + HTML + CSS (no build step),
which keeps the whole project runnable with one command.

```
                ┌────────────────────────── FastAPI app (app/main.py) ──────────────────────────┐
  Browser  ──▶  │  Routers (REST)  ─▶  Services (domain logic)  ─▶  Models (.pt/.pkl) + SQLite   │
  (2 SPAs)      │  auth, climate,      climate, fusion, gridded_analysis, segmentation,          │
                │  gridded, fusion,    detection, disaster, multispectral, lstm_forecast, …       │
                │  hazards, weather,                                                              │
                │  analysis, change,   Ingestion (ingest/): NASA POWER · Open-Meteo · IMD · INSAT │
                │  disaster, dashboard  → NetCDF → regrid 0.25° → cache (data/gridded)            │
                └────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Tech stack (with 2-line explanations)

### Backend & framework
- **Python 3.12** — the single implementation language for the backend, models, and
  data pipelines. Chosen because the entire scientific-Python and deep-learning ecosystem
  lives here, so ingestion, ML, and the API all share one runtime.
- **FastAPI 0.115** — the async web framework that exposes our REST API and serves the
  UIs. It auto-generates interactive OpenAPI docs at `/docs`, which doubles as a live,
  demoable API explorer for judges.
- **Uvicorn 0.34** — the ASGI server that actually runs FastAPI. It gives us hot-reload
  in development and production-grade async request handling in one lightweight process.
- **Pydantic 2.10** — validates and serializes every request/response against typed
  schemas. It guarantees the API never returns malformed data and documents itself.

### Data & storage
- **SQLite (via a custom Mongo-like layer)** — stores users, OTPs, analyses and change
  records in one local file (`storage/bhudarpan.db`). We wrote a thin `insert_one/find/
  update_one` wrapper so the app is storage-agnostic and needs zero DB setup.
- **xarray 2025.1 + netCDF4 1.7** — read, align and manipulate the multi-dimensional
  gridded climate data (lat × lon × time). This is the backbone of ingestion, anomaly
  computation, and data fusion.
- **NumPy / SciPy / scikit-learn** — the numerical core: array math, interpolation,
  statistics, and the classical ML forecaster (gradient-boosted trees). They power the
  anomaly, fusion, and forecasting math throughout the services layer.

### Deep learning & computer vision
- **PyTorch 2.14 + torchvision** — trains and runs our EuroSAT land-cover CNN and the
  LSTM climate forecaster on CPU. CPU-only wheels keep the project laptop-friendly with
  no GPU requirement.
- **OpenCV (headless) + Pillow** — image decoding, resizing, colour-space conversion and
  drawing of segmentation/detection overlays. They handle every pixel operation in the
  satellite pipeline.
- **tifffile + imagecodecs** — decode multispectral GeoTIFF imagery (NIR/SWIR bands)
  that Pillow cannot read. This unlocks the physics-based flood/burn/fire indices.

### Reporting, auth & integrations
- **ReportLab 4.2** — generates the downloadable PDF analysis/alert reports server-side.
  It turns a raw analysis into a formatted, shareable document for authorities.
- **PyJWT + passlib** — issue signed JWT session tokens and hash passwords/OTP codes at
  rest. Together they secure every protected endpoint without storing any secret in clear.
- **requests + imdlib** — fetch live data from NASA POWER / Open-Meteo / IMD sources.
  `imdlib` specifically pulls India Meteorological Department gridded records.
- **GNews / NewsAPI** — optional live weather-news headlines for J&K on the Insights page.
  The app degrades gracefully (shows a "not configured" note) if no key is set.

### Frontend
- **Vanilla JavaScript + HTML5 + CSS3 (no framework, no build)** — both SPAs are hand-
  written for zero build tooling, so anyone can open the file and it just works. Charts,
  heatmaps and maps are drawn with the native `<canvas>` and inline SVG.
- **A React/Vite frontend also exists** in `frontend/` as an optional alternative UI, but
  it is **not required** — the backend already serves the production vanilla-JS apps.

---

## 5. AI / ML models (the part judges love)

### 5.1 EuroSAT Land-Cover CNN — `models/landcover_cnn.pt`
A **residual convolutional network ("ResNet-lite": 4 stages, 17 conv layers, skip
connections + global average pooling, 2.8M parameters)** trained from scratch on the
**EuroSAT** Sentinel-2 dataset (27,000 images, 10 classes). It classifies each image region
into land-cover types, which we group into 5 app classes: Forest, Water, Agriculture,
Urban, Others.
- **Accuracy: 98.33% on the 10-class held-out test set, 99.59% on the 5 grouped app
  classes** (2,700 test images; per-class recall: Forest 99.7%, Water 99.6%,
  Agriculture 99.5%, Urban 99.6%). The previous 3-block CNN scored 95.22% / 98.0% on the
  same split; the new model replaced it only because it won on that identical test set.
- Training recipe: SGD-Nesterov with a one-cycle learning-rate schedule, **CutMix**, label
  smoothing, flips/rotations/crops/colour jitter, and an **exponential moving average (EMA)**
  of the weights — standard modern tricks that reduce over-fitting.
- **Test-time augmentation:** at inference the app averages predictions over 4 rotations
  (0/90/180/270°) — satellite images have no "up", so this adds +0.7 pt accuracy for free
  (97.59% → 98.33%).

### 5.2 CNN-First Hybrid Segmentation — `services/segmentation.py`
Every pixel is first labelled by the CNN (sliding 64×64 windows, overlap-averaged into a
smooth probability map). Colour/texture physics then corrects only what the CNN **cannot
know**, because EuroSAT has no class for it:
- **snow/ice, grey rock, dune sand and barren (vegetation-free) landscapes → bare ground**,
  so deserts and glaciers are never painted as farmland;
- the CNN's water must be smooth and not bright, and its "Industrial" next to ice is
  rejected, so mountains are never painted as lakes or cities;
- deep/dark or clearly blue glass-smooth water the CNN misses is added, and dense
  non-European towns (a *density* of roofs and roads among street trees) are recovered.
- The CNN is fed the image **before** contrast enhancement (its training domain) — the
  enhanced image is only used for the physical tests. Feeding it the enhanced image drops
  it from 98.5% to 65–78%.

**Measured accuracy of the whole pipeline** (`scripts/eval_segmentation.py` →
`models/segmentation_eval.json`), versus the previous rule-first segmenter:

| Test | Previous | Now |
|---|---|---|
| 2,700 EuroSAT held-out tiles, run through the full app pipeline | 20.2% | **84.8%** |
| 31 hand-labelled regions in real J&K / world scenes (lake, city, riverbed, rock, snow) | 37.3% | **66.7%** |
| 21 whole-scene sanity checks (e.g. "Sahara ≥85% bare", "open sea ≥80% water") | 13/21 | **16/21** |

- Why the pipeline is below the CNN's 98%: on 10 m EuroSAT tiles, harvested brown fields
  look exactly like desert, so the bare-ground guard costs some Agriculture recall — a
  deliberate trade to avoid hallucinating farmland on deserts and mountains. The CNN alone
  scores 98.5% on EuroSAT but only 55% on the real scenes (8/21 checks) for that reason.
- Honest remaining weaknesses: Dal Lake's algae-green water is partly missed (11% vs ~20%),
  very dense Indian old-city cores are partly under-called, and Venice's red-roofed old
  town reads as farmland.

### 5.3 14-Day Skill-Optimised Ensemble Forecast — `services/climate.py` + `scripts/backtest_forecast.py`
The headline J&K forecast is an **ensemble of three members** around a trend-adjusted
climatology: an **LSTM** (`models/lstm_climate.pt`, reads the last 30 days of anomalies),
**gradient-boosted regression trees** (`services/ml_forecast.py`), and **damped persistence**
(today's anomaly fading with lead time). The blend weights are fitted **per lead day**
(non-negative least squares) so each lead uses whatever actually works at that range —
the ML models dominate days 1–3, persistence and climatology take over after that.
- Everything is scored in one **unified 14-day backtest**: 715 issue dates in 2022–2023
  (weights fitted on 2021, warming-trend slope fitted on ≤2020 only — no leakage).
- **Temperature: RMSE 2.13 °C over days 1–14, a +26.3% skill gain over climatology**
  (the LSTM alone scores +17.5%, GBRT alone +6.1%).
- **Rainfall: RMSE 5.06 mm/day, +1.5% over climatology.** Daily rainfall is close to
  unpredictable beyond ~3 days anywhere in the world; we report this honestly instead of
  quoting a 1-day-ahead number. The uncertainty band shown is the backtest RMSE for each lead.
- The forecast is **seeded from live data**: the record is extended to ~3 days ago with NASA
  POWER, so "observed" days on the chart are real recent observations.

### 5.4 Per-Cell Map Forecaster — `services/grid_ml_forecast.py`
The forecast heat-map (every ~0.5° grid cell) uses a **daily climatology per cell plus an
optimised persistence anomaly** whose decay factor is fitted for each lead day. We also
trained a GBRT per-cell model, but it lost to this simpler method in testing, so it is kept
only for comparison — a real example of choosing the model by evidence, not by hype.
- Beats climatology at **every** lead: temperature +36.7% (day 1), +15.0% (day 3), +6.0%
  (day 7), +3.4% (day 14); rainfall +4.6% on day 1, ≈0 after. It also beats naive persistence.

### 5.5 Skill-Gating (a key differentiator)
Every forecast is compared against the climatology baseline before it is shown; if a model
can't beat "the seasonal average," the twin falls back to climatology. This is an honesty
mechanism — **we never present a forecast that is worse than doing nothing**, which is
exactly what a scientific reviewer wants to hear.

### 5.6 Multi-Source Data Assimilation (Optimal Interpolation / BLUE) — `services/fusion.py`
Two independent reanalyses — **NASA POWER (MERRA-2)** and **Open-Meteo (ERA5)** — are
merged pixel-by-pixel with the **Best Linear Unbiased Estimator (BLUE)**: each source's
error variance, bias and the correlation between their errors are measured against the IMD
station record, the biased source is corrected, and weights are chosen to minimise the
fused error. We also publish the inter-source spread (a live uncertainty map).
- Validated against IMD: **fused rainfall error is 15.5% lower and fused temperature error
  3.9% lower than the best single source.**
- IMD station data currently ends in 2023, so the error statistics are calibrated on the
  overlap period and then applied to the live window — exactly how operational centres run
  optimal interpolation.

### 5.7 Disaster Detection & Spectral Indices — `services/disaster.py` + `services/multispectral.py`
Drought/flood/fire detection uses **physics-based spectral indices** computed from the
image bands: NDWI/MNDWI (water), NDVI (vegetation), NBR/NBR2 & dNBR (burn severity),
and an active-fire test on the SWIR band. On multispectral GeoTIFFs these use true
NIR/SWIR reflectance; on RGB images we approximate them.
- The output is a severity-graded detection with an **authority-alert payload** (what,
  where, how severe, exposure) that could be routed to disaster-management officials.
- **Baseline-aware:** given coordinates, the app fetches today's Esri satellite tile as a
  pre-event baseline. If the baseline already holds a lake/sea/reservoir, total water is
  *not* treated as a flood — only a measured rise is (so Dal Lake or the Mumbai coast no
  longer raise false flood alerts). Deserts are recognised as arid from the segmenter's
  bare-ground share, and flagged as a persistent condition when the baseline is equally arid.
- Checked on 13 test scenes (fire, flood, city, lakes, sea, reservoir, lagoon, delta,
  glaciers, Alps, Sahara, Thar): 11 give the expected call; the other two report a real
  water difference between the uploaded image and today's baseline imagery.

### 5.8 Change Detection — `services/change_detection.py`
Given a "before" and "after" image of the same area, it computes per-class land-cover
deltas and a change map highlighting where the ground actually changed. This is how you
quantify deforestation, urban sprawl, or post-flood/post-fire damage.
- Results include a changed-percentage, class transition table, and a visual change
  overlay, all served as an API response the UI renders.

---

## 6. Data sources (with 2-line context)

- **NASA POWER** — open, global, near-real-time daily meteorology (temperature, rainfall,
  radiation) on a regional grid. It's our primary always-available live feed and needs no
  account, which makes the twin demoable anywhere.
- **Open-Meteo (ERA5)** — a second independent reanalysis of the same variables. Having a
  second source is what makes the multi-source **fusion** and uncertainty maps possible.
- **IMD (India Meteorological Department, via `imdlib`)** — India's official gridded
  rainfall/temperature record. It is our **ground-truth for validating** the fused field.
- **ISRO / MOSDAC — INSAT-3D L2B** — geostationary satellite products (Land/Sea Surface
  Temperature, rainfall) at ~4 km. Used for surface fusion and nowcast blending; requires
  a MOSDAC account, so it's marked "ingesting/ready" rather than always-live.
- **EuroSAT (Sentinel-2)** — the labelled satellite-image dataset used to **train** the
  land-cover CNN. It is committed as `Backend/data/eurosat/EuroSAT.zip`.

**Coverage:** the historical record spans **18,262 daily records (1973 → 2023, ~50 years)**,
stored in `models/jk_state_daily_50y.csv`, which anchors every anomaly and climatology.

---

## 7. Feature-by-feature walkthrough

### Climate Digital Twin (`/`)
- **Overview** — live current-state KPIs (rainfall & temperature anomaly, soil moisture,
  drought class) computed from the latest ingested grid, auto-refreshing. It is the
  "at-a-glance health check" of the region.
- **Climate Map** — an interactive district-level map of rainfall/temperature/soil layers.
  It spatialises the anomalies so you can see *where* in J&K the stress is.
- **Forecast** — 14-day AI forecast with real dates, seasonal continuity, and skill vs
  climatology shown alongside. It answers "what happens next" with an honesty score.
- **Hazards** — drought, heatwave, and monsoon analytics with explainable indices. Each
  hazard has its own endpoint and a judge-explainable definition (e.g. SPI-based drought).
- **What-If Simulator** — adjust rainfall/temperature and instantly see downstream impacts
  on soil moisture, crop-water stress, reservoir inflow, and sector risk (agri, hydropower,
  water supply). It turns the twin into a planning tool, not just a dashboard.
- **Data & Models** — the provenance page: real-time KPIs (records, datasets, models,
  mean skill), the live gridded-field heatmap, multi-source assimilation with per-district
  fused values and an uncertainty map, dataset registry, and the model registry.
- **Insights** — auto-generated advisories from the current state, plus **live weather**
  across 6 J&K stations and **live J&K weather news** headlines.

### Satellite Image Intelligence (`/satellite`)
- **Analyse** — upload an image → land-cover segmentation + object detection + a
  downloadable PDF report. This is the core CV pipeline judges can try live.
- **Change** — upload before/after → change map + per-class deltas. Quantifies real change
  on the ground between two dates.
- **Disaster** — upload a scene → drought/flood/fire detection with severity and an
  authority-alert payload. This is the "act on it" step of the twin.
- **Region / Scenario / Forecast / Dashboard / Reports** — the satellite module's own
  navigation mirroring the twin, plus a user dashboard and saved-report history.

---

## 8. Backend services (the domain logic layer)

Each file in `Backend/app/services/` owns one responsibility:

- **climate.py** — computes the live current state (anomalies, soil, drought class),
  the 14-day forecast, and the what-if scenario. It's the brain of the climate twin.
- **gridded_analysis.py** — turns raw grids into anomalies (value − climatology) for any
  variable/region. Every anomaly number in the UI flows through here.
- **fusion.py** — the optimal-interpolation (BLUE) data assimilation and its validation/spread.
  Aligns the two reanalyses on a common contemporaneous grid before merging.
- **lstm_forecast.py / ml_forecast.py / grid_ml_forecast.py** — the forecasting models
  (LSTM and gradient-boosted ensemble members, per-cell optimised persistence) plus their
  skill gating; the ensemble weights come from `scripts/backtest_forecast.py`.
- **hazards.py** — drought/heatwave/monsoon indices and analytics from the 50-year record.
- **segmentation.py / landcover_model.py** — the hybrid spectral-texture + CNN land-cover
  classifier for the satellite module.
- **detection.py** — object detection (buildings, water bodies, roads, vegetation, farmland)
  on the segmented scene.
- **disaster.py / multispectral.py** — spectral-index disaster detection and multispectral
  GeoTIFF band handling (NIR/SWIR).
- **change_detection.py / satellite_fusion.py** — before/after change mapping and image
  fusion helpers.
- **weather_live.py** — live 6-station J&K weather via Open-Meteo (10-min cache).
- **weather_news.py** — live J&K weather-news headlines via GNews/NewsAPI (30-min cache).
- **report.py** — ReportLab PDF generation. **email_service.py** — SMTP OTP delivery.
- **refresh.py** — the near-real-time background scheduler: re-ingests all seven data
  layers every 6 hours (and at startup when stale), then pre-warms the model caches.
- **engine.py / preprocessing.py / constants.py** — shared image pipeline + config helpers.

---

## 9. API reference (grouped)

Full interactive docs are always live at **`/docs`**. Summary:

| Group | Endpoints | Auth |
|---|---|---|
| **Climate** | `GET /api/climate/{current,data,districts,forecast,insights}`, `POST /api/climate/whatif` | public |
| **Gridded** | `GET /api/gridded/{vars,status,anomaly,field,forecast,forecast/skill}` | public |
| **Fusion** | `GET /api/fusion/{status,field,surface-temp}` | public |
| **Hazards** | `GET /api/hazards`, `/api/hazards/{analytics,drought,heatwave,monsoon}` | public |
| **Weather** | `GET /api/weather/{live,news}` | public |
| **Ingest** | `GET /api/ingest/status`, `POST /api/ingest/refresh` | public |
| **Auth** | `POST /api/auth/{register,login,request-otp,verify-otp}`, `GET /api/auth/me` | mixed |
| **Satellite** | `POST /api/analysis`, `GET /api/analysis`, `POST /api/analysis/{id}/report`, `POST /api/change`, `GET /api/change`, `POST /api/disaster/detect` | protected |
| **Dashboard / System** | `GET /api/dashboard`, `GET /api/health` | mixed |

---

## 10. Team roles & ownership

The project is split into four ownership areas (matching the hand-off bundles). Every
part is independently runnable but integrates into the whole.

### Member A — Climate-Core
**Owns:** the climate science engine and forecasting.
- Files: `services/climate.py`, `gridded_analysis.py`, `hazards.py`, `lstm_forecast.py`,
  `ml_forecast.py`, `grid_ml_forecast.py`, `routers/climate.py`, `hazards.py`, `gridded.py`,
  `models/*.pt`, `scripts/train_lstm.py`.
- **Talk track:** anomalies, the 14-day forecast, skill-gating vs climatology, and the
  hazard indices (drought/heatwave/monsoon).

### Member B — Satellite-CV
**Owns:** the computer-vision / satellite intelligence module.
- Files: `services/segmentation.py`, `landcover_model.py`, `detection.py`, `disaster.py`,
  `multispectral.py`, `change_detection.py`, `routers/analysis.py`, `change.py`, `disaster.py`,
  `scripts/train_landcover.py`, `train_disaster.py`.
- **Talk track:** the 98.33%/99.59% EuroSAT ResNet-lite CNN (up from 95.22%/98.0%), why segmentation doesn't hallucinate,
  spectral indices (NDWI/NDVI/NBR), and the authority-alert output.

### Member C — Auth-Infra
**Owns:** authentication, security, storage, and data ingestion pipeline.
- Files: `routers/auth.py`, `security.py`, `deps.py`, `database.py`, `config.py`,
  `email_service.py`, `services/refresh.py`, `ingest/` (power.py, openmeteo.py, imd.py,
  mosdac.py, pipeline.py, regrid.py), `main.py`.
- **Talk track:** JWT + hashed email-OTP auth, the SQLite storage layer, and the
  NetCDF ingestion → regrid → cache pipeline.

### Member D — Frontend-Fusion
**Owns:** the user interfaces and the data-fusion presentation.
- Files: `webapp/index.html`, `webapp/satellite.html`, `services/fusion.py`,
  `satellite_fusion.py`, `routers/fusion.py`, `weather_live.py`, `weather_news.py`,
  `routers/weather.py`, `dashboard.py`, `report.py`.
- **Talk track:** the two SPAs, the multi-source assimilation view, live weather/news,
  and the PDF reporting.

> **Integration rule:** everyone codes against the REST API contract in Section 9, so any
> part can be developed and tested in isolation and still plug into the running whole.

---

## 11. Judge FAQ (anticipated questions & ready answers)

**Q: Is this real data or mock data?**
A: 100% real. We ingest live NASA POWER and Open-Meteo grids, validate against the IMD
50-year record (18,262 daily observations), and every model number comes from a metrics
file in the repo. Nothing on screen is hard-coded.

**Q: What makes it a "digital twin" and not just a dashboard?**
A: A twin mirrors the real system's state *and* projects it forward. We continuously
assimilate live data into a fused state, forecast the next 14 days with skill-gated AI,
and let you run what-if scenarios — a dashboard only shows the past.

**Q: How accurate are your models, honestly?**
A: The land-cover CNN is 98.33% (10-class) / 99.59% (grouped) on 2,700 held-out images, and
the full segmentation pipeline that users actually see scores 84.8% on those tiles and 66.7% on
hand-labelled real J&K/world scenes (it deliberately trades a little EuroSAT farmland recall to
avoid painting deserts and glaciers as farmland). Over a full 14-day horizon,
backtested on 715 forecasts from 2022–2023, the temperature forecast beats climatology by
26.3%. Rainfall beats it by only 1.5%, because daily rain is hard to predict more than a few
days out, and we say so. We *never* show a forecast that's worse than climatology. That's the
skill-gating safeguard.

**Q: Why should we trust the fused climate field?**
A: We combine two independent reanalyses with optimal interpolation (BLUE: bias-corrected,
error-covariance-aware weights) — the same family of methods weather agencies use. Against the
IMD station record the fused field is 15.5% (rain) and 3.9% (temperature) more accurate than
the best single source, and we publish the inter-source disagreement as a live uncertainty map.

**Q: How fresh is the data?**
A: Every panel is at most ~3 days old: NASA POWER publishes with a ~3-day delay, and
Open-Meteo is same-day. A background scheduler refreshes all seven data layers every
6 hours (and at startup if they are stale); the "Live" badge triggers an on-demand refresh.

**Q: How does disaster detection work?**
A: We compute physics-based spectral indices — NDWI/MNDWI for water/flood, NBR/dNBR for
burn severity, and a SWIR active-fire test — from the image bands. On multispectral
GeoTIFFs these use true NIR/SWIR reflectance, giving a severity-graded, explainable alert.

**Q: Does it need a GPU or cloud?**
A: No. Everything runs on CPU in one Python process with a local SQLite file. It installs
into a project-local virtual environment and runs with a single command — no external DB,
no GPU, no cloud account required.

**Q: What's the tech stack in one breath?**
A: FastAPI + Python 3.12 backend, PyTorch/scikit-learn models, xarray/netCDF for gridded
data, SQLite storage, JWT+OTP auth, and dependency-free vanilla-JS front-ends served by
the same backend.

**Q: Is it secure?**
A: Yes — JWT session tokens, passwords and OTP codes hashed at rest, rate-limited OTP
sending to prevent abuse, and all secrets kept in an un-committed `.env`. Protected
endpoints reject unauthenticated requests.

**Q: Can it scale / go to production?**
A: The architecture is deployment-ready (secure endpoints, env-driven config, graceful
fallbacks). SQLite can be swapped for a server DB behind the same interface, and the
async FastAPI layer handles concurrent traffic.

**Q: What would you build next?**
A: Real-time INSAT/MOSDAC fusion at full cadence, SMS/push alerts to district officials,
and per-village downscaling of the forecast grid.

---

## 12. Running it (quick reference)

```bash
cd Backend
python3.12 -m venv .venv            # Windows: py -3.12 -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py                       # serves http://localhost:8000
```

Open `http://localhost:8000` (twin), `http://localhost:8000/satellite` (satellite module),
`http://localhost:8000/docs` (API). No configuration required — see the root
[README.md](../README.md) for full details, and [ARCHITECTURE.md](ARCHITECTURE.md) for the
system design.

---

*Bhū-Darpan — India's climate, mirrored in real time.*
