"""Viva demo preset endpoints for examination presentations and offline testing."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, status
from PIL import Image

from ..config import settings
from ..database import db

router = APIRouter(prefix="/api/demo", tags=["demo"])

PRESETS_DIR = settings.base_dir / "data" / "demo_presets"
MANIFEST_PATH = PRESETS_DIR / "manifest.json"
TEST_IMAGES_DIR = settings.base_dir.parent / "test_images"


def _ensure_demo_assets(preset_id: str) -> None:
    """Ensures static image assets for the preset exist in storage/uploads and storage/masks."""
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.masks_dir.mkdir(parents=True, exist_ok=True)

    # 1. Dal Lake Flood Preset
    if preset_id == "dal_lake_flood_2014":
        orig_target = settings.uploads_dir / "demo_dal_lake_flood_2014.png"
        seg_target = settings.masks_dir / "demo_dal_lake_flood_2014_seg.png"
        det_target = settings.masks_dir / "demo_dal_lake_flood_2014_det.png"

        src_jpg = TEST_IMAGES_DIR / "dal_lake_srinagar.jpg"
        if src_jpg.exists() and not orig_target.exists():
            img = Image.open(src_jpg).convert("RGB")
            img.save(orig_target, format="PNG")

            # Generate representative segmentation mask (Water=Blue, Urban=Red, Forest=Green, Agri=Yellow)
            import numpy as np
            arr = np.array(img)
            h, w = arr.shape[:2]
            mask = np.zeros((h, w, 3), dtype=np.uint8)
            # Water mask (center/lake)
            mask[:, :] = [46, 125, 50]  # default Forest
            mask[:int(h*0.7), :int(w*0.35)] = [229, 57, 53]  # Urban left
            # Water in Dal Lake
            center_y, center_x = int(h * 0.45), int(w * 0.55)
            y, x = np.ogrid[:h, :w]
            dal_lake_zone = ((x - center_x) ** 2) / (0.22 * w) ** 2 + ((y - center_y) ** 2) / (0.42 * h) ** 2 <= 1
            mask[dal_lake_zone] = [21, 101, 192]  # Water
            Image.fromarray(mask).save(seg_target, format="PNG")

            # Detection overlay
            overlay = arr.copy()
            overlay[dal_lake_zone] = (overlay[dal_lake_zone] * 0.5 + np.array([30, 144, 255]) * 0.5).astype(np.uint8)
            Image.fromarray(overlay).save(det_target, format="PNG")

    # 2. Jammu Decadal Expansion Preset
    elif preset_id == "jammu_expansion_2023":
        before_target = settings.uploads_dir / "demo_jammu_expansion_before.png"
        after_target = settings.uploads_dir / "demo_jammu_expansion_after.png"
        change_target = settings.masks_dir / "demo_jammu_expansion_change.png"

        src_jpg = TEST_IMAGES_DIR / "jammu_city.jpg"
        if src_jpg.exists() and not after_target.exists():
            img = Image.open(src_jpg).convert("RGB")
            img.save(after_target, format="PNG")
            # Create synthetic "before" image (more green/vegetation, less urban)
            import numpy as np
            arr = np.array(img)
            before_arr = arr.copy()
            # Boost green in outskirts to represent historical farmland
            before_arr[:, :, 1] = np.clip(before_arr[:, :, 1].astype(int) + 25, 0, 255).astype(np.uint8)
            Image.fromarray(before_arr).save(before_target, format="PNG")

            # Change map: red for changed pixels
            diff = np.abs(arr.astype(int) - before_arr.astype(int)).sum(axis=-1)
            change_mask = np.zeros_like(arr)
            change_mask[diff > 20] = [229, 57, 53]  # Red = changed
            change_mask[diff <= 20] = [46, 125, 50]  # Green = stable
            Image.fromarray(change_mask).save(change_target, format="PNG")

    # 3. Chenab Wildfire Preset
    elif preset_id == "chenab_wildfire_burn":
        orig_target = settings.uploads_dir / "demo_chenab_wildfire.png"
        seg_target = settings.masks_dir / "demo_chenab_wildfire_seg.png"
        det_target = settings.masks_dir / "demo_chenab_wildfire_det.png"

        src_jpg = TEST_IMAGES_DIR / "world_flood_delta.jpg"
        if src_jpg.exists() and not orig_target.exists():
            img = Image.open(src_jpg).convert("RGB")
            img.save(orig_target, format="PNG")

            import numpy as np
            arr = np.array(img)
            h, w = arr.shape[:2]
            det_overlay = arr.copy()
            # Overlay hazard burn zone
            burn_zone = (arr[:, :, 0] > 70) & (arr[:, :, 1] < 120)
            det_overlay[burn_zone] = (det_overlay[burn_zone] * 0.4 + np.array([255, 69, 0]) * 0.6).astype(np.uint8)
            Image.fromarray(det_overlay).save(det_target, format="PNG")
            Image.fromarray(arr).save(seg_target, format="PNG")


@router.get("/presets")
def list_presets() -> dict[str, Any]:
    """Returns the manifest of pre-packaged examination demonstration scenarios."""
    if not MANIFEST_PATH.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo presets manifest not found.")
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return manifest
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to load manifest: {exc}")


@router.post("/load/{preset_id}")
def load_preset(preset_id: str) -> dict[str, Any]:
    """
    Instantly provisions demo assets, hydrates the local database,
    and returns the fully hydrated payload ready for client-side rendering.
    """
    preset_path = PRESETS_DIR / f"{preset_id}.json"
    if not preset_path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Preset '{preset_id}' not found. Available: dal_lake_flood_2014, jammu_expansion_2023, chenab_wildfire_burn",
        )

    try:
        payload = json.loads(preset_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Corrupt preset payload: {exc}")

    # Ensure associated image files exist
    try:
        _ensure_demo_assets(preset_id)
    except Exception:
        # Asset auto-creation is non-fatal if images aren't present
        pass

    category = payload.get("category", "analysis")
    payload["owner"] = "demo_examiner"

    # Persist in SQLite under the appropriate collection
    if category == "analysis":
        db.analyses.insert_one(payload)
        # Also store in disasters collection if it contains disaster metadata
        if "severity" in payload:
            db.disasters.insert_one(payload)
    elif category == "change":
        db.changes.insert_one(payload)
    elif category == "disaster":
        db.disasters.insert_one(payload)

    return {
        "status": "success",
        "preset_id": preset_id,
        "category": category,
        "document": payload,
    }


@router.post("/reset")
def reset_demo() -> dict[str, str]:
    """Removes injected demo records from the database."""
    db.analyses.delete_one({"owner": "demo_examiner"})
    db.changes.delete_one({"owner": "demo_examiner"})
    db.disasters.delete_one({"owner": "demo_examiner"})
    return {"status": "success", "message": "Demo data reset successfully."}
