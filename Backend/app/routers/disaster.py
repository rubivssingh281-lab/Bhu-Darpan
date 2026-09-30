"""Disaster detection & authority alerting routes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from ..config import settings
from ..database import db
from ..deps import get_current_user
from ..services import basemap, disaster

router = APIRouter(prefix="/api/disaster", tags=["disaster"])

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"}


@router.post("/detect")
async def detect(
    file: UploadFile = File(...),
    before: Optional[UploadFile] = File(None),
    lat: Optional[float] = Form(None),
    lon: Optional[float] = Form(None),
    region: Optional[str] = Form(None),
    use_basemap: bool = Form(False),
    extent_km: float = Form(3.0),
    user: dict = Depends(get_current_user),
):
    if file.content_type not in _IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Unsupported image type: {file.content_type}")
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    location = {"lat": lat, "lon": lon} if (lat is not None and lon is not None) else None

    baseline_url = None
    baseline_source = None
    before_data = await before.read() if before is not None else None
    # Auto-fetch the pre-event baseline from the Esri satellite basemap at the given
    # coordinates when the user asked for it and didn't upload a "before" image.
    if before_data is None and use_basemap:
        if location is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Enter latitude & longitude to fetch a satellite baseline.")
        before_data = await run_in_threadpool(
            basemap.fetch_baseline, lat, lon, max(0.2, extent_km / 2.0))
        if before_data is None:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                                "Could not fetch the satellite baseline for those coordinates. "
                                "Try again or upload a 'before' image.")
        # persist the fetched baseline so the UI can show what it compared against
        bid = uuid.uuid4().hex
        (settings.masks_dir / f"{bid}_baseline.jpg").write_bytes(before_data)
        baseline_url = f"/storage/masks/{bid}_baseline.jpg"
        baseline_source = f"Esri World Imagery · ~{extent_km:g} km box @ {lat}, {lon}"

    result = await run_in_threadpool(
        disaster.detect, data, before_data,
        region or "Jammu & Kashmir", location,
    )
    if baseline_url:
        result["baseline_url"] = baseline_url
        result["baseline_source"] = baseline_source

    # persist a compact record so the Disaster tab can show a scan history
    rid = uuid.uuid4().hex
    result["id"] = rid
    scene_name = (file.filename or "scene").rsplit(".", 1)[0][:80]
    db.disasters.insert_one({
        "id": rid,
        "owner": user["id"],
        "name": scene_name,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "region": result.get("region"),
        "mode": result.get("mode"),
        "primary": result.get("primary"),
        "severity": result.get("severity"),
        "affected_area_pct": result.get("affected_area_pct"),
        "overlay_url": result.get("overlay_url"),
        "location": location,
    })
    return result


@router.get("/history")
def history(user: dict = Depends(get_current_user)):
    """Recent disaster scans for the signed-in user, newest first."""
    rows = db.disasters.find({"owner": user["id"]})
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    keep = ("id", "name", "created_at", "region", "mode", "primary",
            "severity", "affected_area_pct", "overlay_url", "location")
    return [{k: r.get(k) for k in keep} for r in rows[:50]]
