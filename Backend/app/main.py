"""Bhū-Darpan backend — FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import settings
from .database import db
from .routers import analysis, auth, change, climate, dashboard, disaster, fusion, gridded, hazards, ingest, weather


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .services import refresh
    refresh.start_scheduler()          # near-real-time auto-refresh (if AUTO_REFRESH_HOURS > 0)
    yield


app = FastAPI(
    title="Bhū-Darpan — Satellite Image Analysis API",
    version=__version__,
    description="AI-based satellite image analysis: land-cover segmentation, "
                "object detection, change detection and automated reporting.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve stored artefacts (images, masks, reports) at /storage
app.mount("/storage", StaticFiles(directory=str(settings.storage_dir)), name="storage")

app.include_router(auth.router)
app.include_router(analysis.router)
app.include_router(change.router)
app.include_router(dashboard.router)
app.include_router(climate.router)
app.include_router(gridded.router)
app.include_router(hazards.router)
app.include_router(ingest.router)
app.include_router(fusion.router)
app.include_router(weather.router)
app.include_router(disaster.router)


@app.get("/api/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "database": db.info(),
        "classes": ["Forest", "Water", "Agriculture", "Urban", "Others"],
    }


_WEBAPP_DIR = settings.base_dir / "webapp"


@app.get("/", include_in_schema=False)
def root():
    """Serve the climate digital-twin single-page app."""
    page = _WEBAPP_DIR / "index.html"
    if page.exists():
        return FileResponse(str(page))
    return JSONResponse({"name": "Bhū-Darpan Climate Digital Twin API", "docs": "/docs"})


@app.get("/satellite", include_in_schema=False)
def satellite_app():
    """Serve the satellite image-analysis single-page app."""
    page = _WEBAPP_DIR / "satellite.html"
    if page.exists():
        return FileResponse(str(page))
    return JSONResponse({"error": "satellite app not found"})


@app.get("/logo.png", include_in_schema=False)
def logo():
    """Bhū-Darpan mission-insignia logo (also used as the favicon)."""
    return FileResponse(str(_WEBAPP_DIR / "logo.png"), media_type="image/png")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(str(_WEBAPP_DIR / "logo.png"), media_type="image/png")


@app.get("/auth-map.jpg", include_in_schema=False)
def auth_map():
    """Real Esri satellite imagery of the Jammu & Kashmir pilot region (login background)."""
    return FileResponse(str(_WEBAPP_DIR / "jk_satellite.jpg"), media_type="image/jpeg")
