# Bhū-Darpan Deployment Guide: Render (Backend) & Vercel (Frontend)

This guide walks you through deploying **Bhū-Darpan** to production using **Render** for the Python/FastAPI backend and **Vercel** for the Vite/React frontend.

---

## 1. System Architecture

```
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│         Vercel (Frontend)       │           │          Render (Backend)       │
│  - Static Web App (HTML/JS/CSS) │  HTTPS    │  - FastAPI + Python 3.12        │
│  - Dual Modules:                │ ────────> │  - Uvicorn ASGI Server          │
│    • / (Climate Digital Twin)   │  /api/*   │  - CPU PyTorch CNN + Analytics  │
│    • /satellite (Satellite EO)  │ /storage/*│  - Hosted at:                   │
│  - Hosted at:                   │           │    https://<app>.onrender.com   │
│    https://<your-app>.vercel.app│           │                                 │
└─────────────────────────────────┘           └─────────────────────────────────┘
```

- **Frontend on Vercel**: Zero-build static CDN hosting for `index.html` (Climate Twin) and `satellite.html` (Satellite EO). `vercel.json` proxies API and storage requests to Render.
- **Backend on Render**: Linux container running FastAPI with CPU-optimized PyTorch models, scientific libraries (SciPy, OpenCV headless, xarray), and SQLite storage.

---

## 2. Complete Project Folder Structure

```
Bhu-Darpan/
├── render.yaml                 # Render Blueprint for 1-click backend deployment
├── .python-version             # Specifies Python 3.12 for Render builder
├── .gitignore                  # Git exclusions (excludes .env, venvs, large temporary files)
├── README.md                   # Main project documentation
├── start-backend.ps1           # Local dev startup for backend
├── start-frontend.ps1          # Local dev startup for frontend (http.server 8010)
│
├── Backend/                    # FASTAPI BACKEND (Deploys to Render)
│   ├── app/                    # Application source code
│   │   ├── main.py             # FastAPI entrypoint, CORS & route registration
│   │   ├── config.py           # Settings & env variable parsing
│   │   ├── database.py         # SQLite / storage engine
│   │   ├── deps.py             # Auth & dependency injection
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── security.py         # JWT tokens & password hashing
│   │   ├── routers/            # API endpoints (/api/analysis, /api/climate, etc.)
│   │   └── services/           # ML inference, CV segmentation, ETL logic
│   ├── data/                   # Climate caches and regional GeoTIFF/NetCDF data
│   ├── models/                 # Pretrained weights (*.pt, *.csv, *.json)
│   ├── storage/                # Runtime user uploads, masks, and generated reports
│   ├── webapp/                 # Complete single-page apps (index.html, satellite.html)
│   ├── .env.example            # Reference environment variables for backend
│   ├── .python-version         # Python version lock for Render
│   ├── Procfile                # Web process definition for Render/PaaS
│   ├── requirements.txt        # Python dependencies (with PyTorch CPU index)
│   └── run.py                  # Local entrypoint script
│
├── frontend/                   # STATIC WEBAPP (Deploys to Vercel)
│   ├── index.html              # Climate Digital Twin application
│   ├── satellite.html          # Satellite Image Analysis application
│   ├── logo.png                # Brand logo & favicon
│   ├── jk_satellite.jpg        # Region imagery
│   └── vercel.json             # Proxy rewrites (/api/* and /storage/* to Render)
│
└── docs/                       # Project documentation & slide decks
    └── DEPLOYMENT.md           # This deployment guide
```

---

## 3. Step 1: Deploy Backend on Render

Deploy the Backend first so you have your Render URL ready to plug into Vercel.

### Option A: 1-Click Blueprint Deploy (Recommended)
1. Push your repository to **GitHub**.
2. Log in to [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** > **Blueprint**.
4. Connect your GitHub repository.
5. Render detects `render.yaml` automatically and configures:
   - Root Directory: `Backend`
   - Build Command: `pip install --upgrade pip && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Click **Apply**.

---

### Option B: Manual Web Service Setup
If creating the service manually:
1. On Render, click **New +** > **Web Service**.
2. Select **Build and deploy from a Git repository**.
3. Fill in the following fields:
   - **Name**: `bhu-darpan-backend` (or any name you prefer)
   - **Region**: Oregon (US West) or Frankfurt
   - **Root Directory**: `Backend`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install --upgrade pip && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: `Free`

4. Add **Environment Variables** under the "Environment" tab:
   | Key | Value | Notes |
   |---|---|---|
   | `PYTHON_VERSION` | `3.12.0` | Ensures Python 3.12 is used |
   | `JWT_SECRET` | *(Click "Generate" or enter random 32+ char string)* | Production auth secret |
   | `AUTO_REFRESH_HOURS` | `0` | Disables background scheduler to stay within free-tier RAM |
   | `CORS_ORIGINS` | `https://*.vercel.app,http://localhost:5173,http://localhost:8010` | Allowed origins |

5. Click **Create Web Service**.
6. Once the deploy completes (status: **Live**), copy your Render service URL (e.g., `https://bhu-darpan-backend.onrender.com`).
7. Verify it works by opening `https://<your-render-app>.onrender.com/api/health` in your browser. Expected response:
   ```json
   {"status":"ok","version":"1.0.0","database":"...","classes":["Forest","Water","Agriculture","Urban","Others"]}
   ```

---

## 4. Step 2: Deploy Frontend on Vercel

1. Log in to [Vercel Dashboard](https://vercel.com/).
2. Click **Add New…** > **Project**.
3. Import your GitHub repository (`Bhu-Darpan`).
4. In the **Configure Project** screen:
   - **Project Name**: `bhu-darpan` (or your chosen name)
   - **Framework Preset**: `Other`
   - **Root Directory**: Click **Edit** and select **`frontend`** (or `Backend/webapp`).
5. Under **Build and Output Settings**:
   - No build command needed — the app is a fast, pure HTML5/JavaScript application! Leave build and output settings at default.
6. Check `vercel.json`:
   - `vercel.json` already proxies `/api/*` and `/storage/*` to your backend on Render. If your Render backend URL is different from `https://bhu-darpan-backend.onrender.com`, update the destination URL in `frontend/vercel.json`.
7. Click **Deploy**.
8. In ~15 seconds, your frontend will be live at `https://<your-project>.vercel.app`.

---

## 5. Verifying the Deployment

1. Visit your Vercel URL: `https://<your-app>.vercel.app`.
2. Open Browser Developer Tools (`F12`) > **Network** tab.
3. Check the API requests:
   - Requests should hit `https://<your-backend-name>.onrender.com/api/...`
   - Status code should be `200 OK`.
4. Test navigation:
   - Click between **Overview**, **Forecast**, **Hazards**, and **Satellite Analysis**.
   - Refresh the page on any sub-route (e.g. `/satellite`). It will reload smoothly without a 404 error because `frontend/vercel.json` rewrites requests to `index.html`.

---

## 6. Key Production Details & Gotchas

### 1. Render Free Tier Spin-Down (Cold Start)
- Render's free tier spins down instances after 15 minutes of inactivity.
- The first request after sleep may take ~30-50 seconds while the container boots and loads model weights into memory.
- Subsequent requests will be fast. For portfolio/hackathon presentations, send a request to `/api/health` 1-2 minutes beforehand to wake it up.

### 2. PyTorch Memory Optimization
- In `requirements.txt`, `--extra-index-url https://download.pytorch.org/whl/cpu` forces pip to install the ~150 MB CPU wheel rather than the 2.5 GB GPU CUDA wheel.
- `AUTO_REFRESH_HOURS=0` prevents periodic heavy background downloads from exceeding the 512 MB free tier memory limit.

### 3. Ephemeral File Storage on Free Tier
- On Render's free tier, uploaded test images and generated reports saved to `Backend/storage/` are stored on an ephemeral disk. They persist during the active session but reset if the server restarts. Pretrained models in `Backend/models/` are part of git and are permanent.
