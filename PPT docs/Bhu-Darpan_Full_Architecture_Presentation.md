# Bhū-Darpan (भू-दर्पण) — Comprehensive System Architecture, Tech Stack, & Models Guide
**12-Hour Presentation Master Document**

---

## 1. Executive Summary & Project Overview

**Bhū-Darpan** ("Earth-Mirror") is an advanced, AI-powered **climate digital twin** engineered explicitly for the Jammu & Kashmir region. It features a bundled **satellite image-analysis module** that facilitates high-precision land-cover segmentation, bi-temporal change detection, and disaster detection (drought, flood, fire). 

The platform operates by fusing real-time and historical gridded climate data (sourced from NASA POWER, IMD, and Open-Meteo) with deep-learning predictive models (LSTMs for climate forecasting) and Convolutional Neural Networks (CNNs trained on EuroSAT for land-cover segmentation).

### 1.1 The Core Philosophy
- **Unified Execution:** The entire application (backend API + both web UIs) runs from a **single Python process**.
- **No Global Footprint:** Operates completely in a project-local virtual environment (`.venv`). It does not modify system-wide Python environments.
- **Offline First & Zero-Config:** Runs entirely on CPU without requiring an external database, external API keys, or GPU acceleration. It includes "Dev-OTP" mode for offline authentication.

---

## 2. Comprehensive Technology Stack

The stack is heavily optimized for scientific computing, geospatial processing, machine learning, and rapid API delivery.

### 2.1 Backend & Core Infrastructure
- **Language:** Python 3.12 (Tested and pinned)
- **Web Framework:** FastAPI (High-performance, async RESTful API)
- **ASGI Server:** Uvicorn (Handles asynchronous processing)
- **Authentication:** PyJWT (JSON Web Tokens), passlib (Password hashing)
- **Configuration Management:** python-dotenv

### 2.2 Machine Learning & Deep Learning (AI Stack)
- **Deep Learning Framework:** PyTorch & TorchVision (CPU-optimized builds pinned in requirements)
- **Machine Learning Library:** Scikit-Learn, SciPy
- **Computer Vision:** OpenCV (opencv-python-headless for server environments without GUI dependencies)
- **Data Manipulation:** NumPy
- **Architectures Used:**
  - **U-Net & SegFormer:** Used for detailed land-cover semantic segmentation.
  - **YOLOv11:** Real-time object detection (buildings, roads, rivers).
  - **Siamese CNN:** Bi-temporal change detection comparing historical and current imagery.
  - **LSTM (Long Short-Term Memory):** Time-series climate forecasting.
  - **ResNet:** Residual networks for advanced land-cover candidate models.

### 2.3 Geospatial & Scientific Data Processing
- **Array & Climate Data:** xarray, netCDF4 (For processing multi-dimensional climate grids).
- **Multispectral Image Processing:** tifffile, imagecodecs (Reading GeoTIFFs, NIR/SWIR indices for flood/burn detection).
- **National Data Ingestion:** imdlib (Indian Meteorological Department data extraction), Requests (NASA POWER/Open-Meteo).

### 2.4 Database & Storage
- **File-Backed Local Store:** A bespoke, local file-backed JSON store simulating an SQLite-style interface. Eliminates the need for a running database server (MongoDB gridFS is supported as an optional scale-up).
- **Reporting:** ReportLab (Automated generation of PDF reports with statistics and maps).

### 2.5 Frontend & User Interface
- **Vanilla Approach (Bundled):** HTML5, CSS3, JavaScript. Chart.js for data visualization, Leaflet/MapLibre for interactive map rendering. Served directly by FastAPI.
- **Modern Approach (Optional):** React.js (v18+) powered by Vite, Axios for API integration.

---

## 3. Deep Dive: Machine Learning Models & Artefacts

The intelligence of Bhū-Darpan lies in its ensemble of deep learning models and classical machine learning regressors/classifiers. These are stored locally in the `Backend/models/` directory.

### 3.1 Neural Network Models (.pt - PyTorch)
1. **`landcover_cnn.pt` (~11.2 MB)**
   - **Purpose:** Primary land-cover classification model.
   - **Training:** Trained on the EuroSAT dataset.
   - **Function:** Segments satellite scenes into discrete land-cover categories (Forest, Water, Agriculture, Built-up, etc.).
2. **`landcover_cnn_candidate.pt` & `landcover_cnn_prev.pt`**
   - **Purpose:** Champion-challenger model deployment artifacts. The system trains a candidate ResNet model (`train_landcover_resnet.py`) and promotes it only if it outperforms the current production model on held-out test splits.
3. **`lstm_climate.pt` (~111 KB)**
   - **Purpose:** Time-series climate forecaster.
   - **Function:** Predicts future climate variables (temperature, rainfall) based on historical gridded data sequences.

### 3.2 Classical Machine Learning Models (.pkl - Scikit-Learn)
These models are utilized heavily in the disaster, hazard, and agricultural stress detection modules.
1. **`model_inflow.pkl` (~130.9 MB / Zipped ~31 MB)** - Predicts hydrological inflow for flood forecasting.
2. **`model_crop_stress.pkl` (~24.7 MB)** - Identifies agricultural stress levels based on environmental factors and spectral indices.
3. **`model_drought_classifier.pkl` (~2.5 MB)** - Classifies drought severity using historical precipitation and soil moisture data.
4. **`model_sm.pkl` (~1.6 MB)** - Soil Moisture prediction model.
5. **`model_temp.pkl` & `model_rain.pkl` (~1.5 MB each)** - Localized temperature and rainfall regressors used for granular grid predictions.

### 3.3 Evaluation Metrics & Metadata
- **`segmentation_eval.json`, `landcover_metrics.json`, `lstm_metrics.json`, `forecast_backtest.json`**: Store validation metrics (Accuracy, F1-Score, RMSE) and ensemble weights per-lead for backtested forecasts.

---

## 4. Comprehensive File Architecture

The repository is modularly designed. Here is the complete traversal of the project structure and the role of every file.

### 4.1 Root Directory (`/`)
- `start-backend.ps1`: The primary entry point for Windows. Creates a virtual environment, installs requirements, and runs the FastAPI server.
- `start-frontend.ps1`: Starts the optional Vite React frontend.
- `README.md`: High-level guide and quick start instructions.
- `upload-readme.md`: Documentation for uploading processes.
- `.gitignore` & `LICENSE`: Standard git configuration and project licensing.

### 4.2 The Backend (`Backend/`)
The heart of the application containing all logic, routing, and machine learning inferences.

- **`run.py`**: The development entry point (`python run.py`) wrapping Uvicorn.
- **`requirements.txt`**: Strict pinning of dependencies (FastAPI, PyTorch CPU, xarray, opencv).
- **`.env.example`**: Template for environment variables (`PORT`, `JWT_SECRET`, `AUTO_REFRESH_HOURS`, `SMTP`, `NEWS_API_KEY`).
- **`README-Explain.md`**: Deep dive into the "SatelliteAI" module components, methodology pipeline, and architecture.

#### 4.2.1 Core Application (`Backend/app/`)
- **`main.py`**: FastAPI app instantiation, CORS configuration, mounting static files (the UI), and including API routers.
- **`config.py`**: Pydantic BaseSettings class loading environment variables with zero-config safe defaults.
- **`database.py`**: Implements the local file-backed JSON store simulating an async DB interface.
- **`schemas.py`**: Pydantic models for API request/response validation.
- **`security.py`**: JWT encoding/decoding and password hashing logic.
- **`deps.py`**: FastAPI dependency injection (e.g., getting the current user, db sessions).

#### 4.2.2 API Routers (`Backend/app/routers/`)
Endpoints that expose the system's capabilities.
- `auth.py`: JWT-based Authentication, User Registration, Dev-OTP mechanism.
- `analysis.py`: Handles generic image analysis endpoints.
- `change.py`: Triggers bi-temporal change detection processes.
- `climate.py`: Fetches and serves climate twin data.
- `dashboard.py`: Aggregates statistics for the frontend dashboard.
- `disaster.py`: Endpoints for flood, drought, and fire risk assessment.
- `fusion.py`: Endpoints for fusing climate data with satellite imagery.
- `gridded.py`: Serves raw and processed gridded climate data.
- `hazards.py`: Identifies high-risk geographical zones.
- `ingest.py`: Manually triggers ETL pipelines for external climate data.
- `weather.py`: Live weather reporting and integration with news APIs.

#### 4.2.3 Business Logic & Services (`Backend/app/services/`)
This is where the heavy lifting occurs—running models, processing matrices, and orchestrating pipelines.
- **AI/ML Processing**:
  - `landcover_model.py`: Loads `landcover_cnn.pt` and runs inferences on satellite patches.
  - `segmentation.py`: Orchestrates the U-Net/SegFormer workflows.
  - `detection.py`: YOLOv11 logic for bounding box object detection.
  - `change_detection.py`: Siamese CNN pipeline comparing two temporal images.
  - `lstm_forecast.py`: Generates climate forecasts using the LSTM model.
  - `ml_forecast.py` & `grid_ml_forecast.py`: Classical ML inference pipelines.
- **Geospatial & Climate Processing**:
  - `climate.py`: Extensive logic for handling IMD/NASA POWER data.
  - `gridded_analysis.py`: Multi-dimensional array manipulations using `xarray`.
  - `multispectral.py`: Processes GeoTIFFs, calculating spectral indices (NDVI, NDWI, NBR).
  - `satellite_fusion.py` & `fusion.py`: Combines satellite visual data with mathematical climate grids.
  - `hazards.py` & `disaster.py`: Applies thresholds and models (`model_inflow.pkl`, etc.) to predict extreme events.
- **Utilities**:
  - `basemap.py`: Handles map tile generations.
  - `report.py`: Utilizes ReportLab to generate automated PDF insight reports.
  - `email_service.py`: Sends SMTP emails (or falls back to console printing in dev mode).
  - `weather_live.py` & `weather_news.py`: Fetches real-time context.
  - `refresh.py`: Background worker script that keeps gridded data fresh (`AUTO_REFRESH_HOURS`).
  - `preprocessing.py`: Image radiometric correction, noise removal, and resizing.
  - `engine.py` & `constants.py`: Core system constants and pipeline engine definitions.

#### 4.2.4 Training & MLOps Scripts (`Backend/scripts/`)
Standalone scripts for training, backtesting, and evaluation. **Not required for running the API.**
- `train_landcover.py`: Trains the primary EuroSAT CNN model.
- `train_landcover_resnet.py`: Trains an experimental ResNet architecture. Promotes to production if metrics exceed the baseline.
- `train_lstm.py`: Trains the time-series LSTM forecaster on historical weather data.
- `train_disaster.py`: Transfer learning pipeline for disaster detection.
- `eval_segmentation.py`: Scores the segmentation pipeline against hand-labelled test regions. Outputs `segmentation_eval.json`.
- `backtest_forecast.py`: Runs a 14-day rolling backtest of the climate models, updating `forecast_backtest.json`.
- `populate.py`: The ETL script that downloads, normalizes, and ingests NetCDF/CSV climate grids from external agencies.

#### 4.2.5 Data & Storage Directories
- `Backend/data/gridded/`: Seed climate grids caches (NASA POWER, Open-Meteo).
- `Backend/storage/`: Stores the local DB file, uploaded images, and generated PDF reports at runtime.

#### 4.2.6 Embedded Web App (`Backend/webapp/`)
Served natively by FastAPI at `/` and `/satellite` without Node.js requirements.
- `index.html`: The main Climate Digital Twin dashboard.
- `satellite.html`: The Satellite Image Analysis interface.
- `logo.png` & `jk_satellite.jpg`: Static assets.

### 4.3 Standalone Frontend (`frontend/`)
An optional, highly interactive React/Vite application.
- `package.json` & `vite.config.js`: Node configuration.
- `src/`: React components, hooks, and context for interacting with the FastAPI backend.
- `public/`: Static assets for the React build.
- *(Note: Often kept for deeper UI development while production utilizes the built/embedded webapp).*

---

## 5. Execution Pipeline Methodology

To understand how Bhū-Darpan operates, here is the automated 8-step pipeline applied when data is ingested:

1. **Acquisition:** System pulls satellite imagery (Sentinel-2, public EO) or user uploads, alongside gridded climate data (`refresh.py`, `populate.py`).
2. **Preprocessing (`preprocessing.py`):** Applies radiometric correction, noise removal, and aligns spatial resolution.
3. **AI Segmentation (`segmentation.py`):** Deep learning models segment the images into precise land-cover classes.
4. **Object Detection (`detection.py`):** Detects localized infrastructure (roads, buildings, distinct water bodies).
5. **Change Detection (`change_detection.py`):** Compares temporal data points to highlight urban expansion, deforestation, or glacial retreat.
6. **Climate & Disaster Fusion (`fusion.py`, `disaster.py`):** Cross-references visual data with numerical gridded data (temperature, moisture grids) using Scikit-Learn `.pkl` models to identify anomalies like droughts or floods.
7. **Confidence Scoring:** Assigns reliability percentages to AI predictions.
8. **Visualization & Reporting (`report.py`, `dashboard.py`):** Renders data via Leaflet maps, Chart.js graphs, and generates downloadable PDF summaries.

---

## 6. Future Scalability & Architecture Considerations

- **Database:** While currently using a flat-file JSON store for portability and zero-config deployment, the data access layer (`database.py`) is decoupled. It can be easily migrated to MongoDB (GridFS) as documented in `README-Explain.md` for massive scale.
- **Compute:** The application strictly uses PyTorch CPU wheels to maintain compatibility across all local machines. For enterprise deployment, switching `requirements.txt` to CUDA-enabled PyTorch wheels will instantly accelerate segmentation and LSTM inferences on GPU infrastructure.
- **Event-Driven Alerts:** The `email_service.py` is designed to support real-time infrastructure alerts based on detected environmental changes, ready to be connected to enterprise SMTP or SMS gateways.

---