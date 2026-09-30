"""Satellite image analysis routes: upload & analyse, list, retrieve, report."""
from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, UploadFile, status,
)
from fastapi.concurrency import run_in_threadpool

from ..config import settings
from ..database import db
from ..deps import get_current_user
from ..schemas import AnalysisOut
from ..services import engine, report as report_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"}


@router.post("", response_model=AnalysisOut)
async def create_analysis(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    lat: Optional[float] = Form(None),
    lon: Optional[float] = Form(None),
    clusters: Optional[int] = Form(None),
    user: dict = Depends(get_current_user),
):
    if file.content_type not in _IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Unsupported image type: {file.content_type}")
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

    location = {"lat": lat, "lon": lon} if (lat is not None and lon is not None) else None
    display_name = (name or file.filename or "Untitled").strip()

    doc = await run_in_threadpool(
        engine.analyze_image, data, display_name, user["id"], location, clusters,
    )
    db.analyses.insert_one(doc)
    return doc


@router.get("", response_model=list[AnalysisOut])
def list_analyses(user: dict = Depends(get_current_user)):
    items = db.analyses.find({"owner": user["id"]})
    items.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return items


@router.get("/model")
def model_info():
    """Public: the land-cover model's measured accuracy (CNN held-out test) and the
    end-to-end segmentation pipeline evaluation, straight from the metrics files."""
    from ..services import landcover_model
    return {**landcover_model.model_summary(), "pipeline_eval": landcover_model.pipeline_eval()}


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = db.analyses.find_one({"id": analysis_id, "owner": user["id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return doc


@router.delete("/{analysis_id}")
def delete_analysis(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = db.analyses.find_one({"id": analysis_id, "owner": user["id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    db.analyses.delete_one({"id": analysis_id})
    return {"deleted": analysis_id}


@router.post("/{analysis_id}/report", response_model=AnalysisOut)
def regenerate_report(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = db.analyses.find_one({"id": analysis_id, "owner": user["id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")

    aid = doc["id"]
    report_path = settings.reports_dir / f"{aid}.pdf"
    original = settings.uploads_dir / f"{aid}.png"
    seg = settings.masks_dir / f"{aid}_seg.png"
    det = settings.masks_dir / f"{aid}_det.png"
    report_service.generate_report(doc, report_path, original, seg, det)
    report_url = f"/storage/reports/{aid}.pdf"
    db.analyses.update_one({"id": aid}, {"$set": {"report_url": report_url}})
    doc["report_url"] = report_url
    return doc
