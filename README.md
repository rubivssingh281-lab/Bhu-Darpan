# Bhū-Darpan (भू-दर्पण) — AI Climate Digital Twin for Jammu & Kashmir

> **Bhū-Darpan** ("Earth-Mirror") is an AI-powered **climate digital twin** for the
> Jammu & Kashmir region, bundled with a **satellite image-analysis** module
> (land-cover segmentation, change detection, and drought/flood/fire disaster
> detection). It fuses real gridded climate data (NASA POWER, IMD-style, Open-Meteo)
> with deep-learning forecasters and a EuroSAT-trained land-cover CNN.

The **entire application (backend API + both web UIs) runs from a single Python
process.** There is no separate frontend build step required — FastAPI serves the
web app directly.

---

## TL;DR for an AI agent / first-time runner

Everything installs into a **local virtual environment** inside the project. Nothing
is installed globally and **no system or Program Files directories are touched.**

### Windows (PowerShell)

```powershell
# from the repository root
.\start-backend.ps1
```

That script creates `Backend/.venv`, installs dependencies into it, and starts the
server. Then open **http://localhost:8000**.

### macOS / Linux (or manual Windows)

```bash
cd Backend
python3.12 -m venv .venv                 # isolated env inside the project
# activate it:
#   macOS/Linux:  source .venv/bin/activate
#   Windows:      .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py                            # serves on http://localhost:8000
```

Open **http://localhost:8000** (climate twin) and **http://localhost:8000/satellite**
(satellite module). API docs: **http://localhost:8000/docs**.

**That's it — no config, no database server, no API keys required.** The app ships
with pretrained models and seed climate data, runs on CPU, and falls back to sensible
offline defaults for every optional integration.

---

## 1. What you get out of the box

| Capability | Endpoint / UI | Notes |
|---|---|---|
| Climate digital twin (Overview, Forecast, Hazards, What-If, Insights) | `/` | Live current-state from ingested NASA POWER grids |
| Satellite image analysis (segmentation, detection, change, disaster) | `/satellite` | EuroSAT-trained CNN + spectral indices |
| Interactive API docs (Swagger) | `/docs` | Auto-generated |
| Health check | `/api/health` | Version + DB status |
| Auth (JWT + email OTP) | `/api/auth/*` | Works offline in "dev OTP" mode |

The satellite module (`/satellite`) is behind a sign-in gate. With no SMTP configured,
the app runs in **dev-OTP mode**: sign-up/sign-in codes are printed to the server
console and returned in the API response, so you can log in fully offline.

---

## 2. Requirements

- **Python 3.12** (tested on 3.12.0). Other 3.11+ versions likely work but are untested.
- ~2 GB free disk for the CPU PyTorch wheels and dependencies.
- No GPU required — everything runs on CPU.
- No external database — data is stored in a local file under `Backend/storage/`.
- Git + (optionally) the GitHub CLI `gh` if you want to push.

Check your Python:

```bash
python3.12 --version    # macOS/Linux
py -3.12 --version      # Windows
```

---

## 3. Installation (isolated, non-invasive)

All dependencies go into `Backend/.venv` — a project-local virtual environment. This is
the standard, safe way to install Python packages **without modifying any system-wide
or Program Files locations.** Delete the `.venv` folder to fully uninstall.

```bash
cd Backend
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### If PyTorch fails to install

`requirements.txt` pins CPU builds of `torch` / `torchvision`. If pip cannot find them
for your platform, install them explicitly from the PyTorch CPU index, then re-run the
requirements install:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

---

## 4. Running

```bash
# from Backend/, with the venv active
python run.py
```

- Serves on `http://localhost:8000` with auto-reload.
- Or run without reload: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Change the port via the `PORT` env var (see Configuration).

**Verify it's up:**

```bash
curl http://localhost:8000/api/health
```

Expected: `{"status":"ok", ...}`.

---

## 5. Configuration (all optional)

The app runs with **zero configuration**. To customise, copy the example env file and
edit values — every setting has a safe default:

```bash
cd Backend
cp .env.example .env        # Windows: Copy-Item .env.example .env
```

Key optional settings (`Backend/.env`):

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | HTTP port |
| `JWT_SECRET` | dev value | **Set a long random string for any real deployment** |
| `AUTO_REFRESH_HOURS` | `0` | `>0` enables the background near-real-time data refresh |
| `SMTP_*` | empty | Set to send real OTP emails; empty = offline dev-OTP mode |
| `NEWS_PROVIDER` / `NEWS_API_KEY` | `newsapi` / empty | Optional J&K weather headlines panel (free key from newsapi.org or gnews.io) |

> **Never commit `.env`.** It is gitignored. Secrets belong only in your local `.env`.

---

## 6. Project structure

```
Bhu-Darpan/
├─ Backend/
│  ├─ app/
│  │  ├─ main.py            # FastAPI app; serves the web UIs + mounts routers
│  │  ├─ config.py          # settings (env-driven, zero-config defaults)
│  │  ├─ database.py        # local file-backed store (SQLite-style interface)
│  │  ├─ routers/           # API endpoints (auth, climate, hazards, fusion,
│  │  │                     #   analysis, change, disaster, weather, ingest, …)
│  │  └─ services/          # domain logic: forecasting, gridded analysis,
│  │                        #   segmentation, detection, disaster, multispectral…
│  ├─ webapp/               # the two single-page UIs (index.html, satellite.html)
│  ├─ models/               # pretrained weights the app loads at runtime
│  │                        #   (landcover_cnn.pt, lstm_climate.pt, *.csv) — committed
│  ├─ data/gridded/         # seed climate grids (NASA POWER / Open-Meteo caches)
│  ├─ scripts/              # training / data pipelines (see below)
│  ├─ requirements.txt
│  ├─ run.py                # dev entrypoint: python run.py
│  └─ .env.example
├─ frontend/                # OPTIONAL standalone Vite frontend (not required to run;
│                           #   the backend already serves the UI)
├─ docs/                    # project documentation
├─ start-backend.ps1        # Windows one-command setup + run
├─ start-frontend.ps1       # optional Vite dev server
└─ README.md
```

### Training / data scripts (optional, not needed to run)

Under `Backend/scripts/` (run with the venv active, from `Backend/`):

- `train_landcover.py` — trains the EuroSAT land-cover CNN.
- `train_disaster.py` — transfer-learning disaster-detection pipeline.
- `train_lstm.py` — trains the LSTM climate forecaster.
- `populate.py` — ingests/refreshes gridded climate data.

The **EuroSAT training dataset (~90 MB) is not committed** (see below); the training
scripts download it on demand. **You do not need it to run the app** — the pretrained
`landcover_cnn.pt` is included.

---

## 7. What is intentionally NOT in this repo

To keep the repository lean and within GitHub's limits, `.gitignore` excludes files
that are either regenerable, local, or secret. **None of these are required to run the
app:**

- `Backend/.venv/`, `__pycache__/` — recreated by the install step.
- `Backend/storage/` — local database, uploaded images, generated PDF reports (created at runtime).
- `Backend/data/eurosat/` — the EuroSAT training dataset (downloaded by the training script).
- `Backend/models/*.pkl` — large/unused experimental model artefacts (one is 125 MB, over GitHub's 100 MB limit; the app loads the `.pt`/`.csv` models, which **are** committed).
- `team_zips/` — redundant zipped hand-off copies of the project.
- `.env` — secrets and local config.
- `node_modules/`, `frontend/dist/` — optional-frontend build artefacts.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `torch` won't install | Use the PyTorch CPU index (section 3). |
| Port 8000 in use | Set `PORT` in `.env`, or run uvicorn with `--port 8010`. |
| Can't sign in to `/satellite` | No SMTP configured → the OTP is printed in the server console and returned by the API (dev mode). |
| News panel says "not configured" | Optional — add a free `NEWS_API_KEY` in `.env`. Everything else still works. |
| `python3.12` not found | Install Python 3.12, or use your platform's launcher (`py -3.12` on Windows). |

---

## 9. License

See [LICENSE](LICENSE).
