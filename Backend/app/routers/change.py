"""Change-detection routes: compare two images, list, retrieve."""
from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, UploadFile, status,
)
from fastapi.concurrency import run_in_threadpool

from ..database import db
from ..deps import get_current_user
from ..schemas import ChangeOut
from ..services import engine

router = APIRouter(prefix="/api/change", tags=["change-detection"])

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"}


@router.post("", response_model=ChangeOut)
async def create_change(
    before: UploadFile = File(...),
    after: UploadFile = File(...),
    name: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    for f in (before, after):
        if f.content_type not in _IMAGE_TYPES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"Unsupported image type: {f.content_type}")
    before_data = await before.read()
    after_data = await after.read()
    if not before_data or not after_data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Both images are required")

    display_name = (name or "Change analysis").strip()
    doc = await run_in_threadpool(
        engine.analyze_change, before_data, after_data, display_name, user["id"],
    )
    db.changes.insert_one(doc)
    return doc


@router.get("", response_model=list[ChangeOut])
def list_changes(user: dict = Depends(get_current_user)):
    items = db.changes.find({"owner": user["id"]})
    items.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return items


@router.get("/{change_id}", response_model=ChangeOut)
def get_change(change_id: str, user: dict = Depends(get_current_user)):
    doc = db.changes.find_one({"id": change_id, "owner": user["id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change analysis not found")
    return doc
