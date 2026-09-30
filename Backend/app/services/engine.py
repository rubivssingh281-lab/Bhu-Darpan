"""Pipeline orchestration: run the full analysis on an uploaded image and persist
all artefacts (original, segmentation mask, detection overlay, PDF report)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from ..config import settings
from . import change_detection, detection, preprocessing, report, segmentation


def _save_png(arr: np.ndarray, path: Path) -> None:
    Image.fromarray(arr.astype(np.uint8)).save(path, format="PNG")


def _url(path: Path) -> str:
    rel = path.relative_to(settings.storage_dir).as_posix()
    return f"/storage/{rel}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def analyze_image(data: bytes, name: str, owner: str,
                  location: Optional[dict] = None,
                  n_clusters: Optional[int] = None) -> dict:
    """Full single-image analysis -> persisted analysis document."""
    aid = uuid.uuid4().hex
    arr, raw = preprocessing.preprocess_pair(data)
    h, w = arr.shape[:2]

    seg = segmentation.segment(arr, n_clusters=n_clusters, raw=raw)
    objects, counts, overlay = detection.detect_objects(arr, seg.class_map)

    from . import landcover_model
    model_info = landcover_model.model_summary() if seg.method == "cnn" else {
        "type": "Unsupervised K-Means clustering", "test_accuracy": None,
    }

    original_path = settings.uploads_dir / f"{aid}.png"
    seg_path = settings.masks_dir / f"{aid}_seg.png"
    det_path = settings.masks_dir / f"{aid}_det.png"
    _save_png(arr, original_path)
    _save_png(seg.mask_rgb, seg_path)
    _save_png(overlay, det_path)

    doc = {
        "id": aid,
        "owner": owner,
        "name": name,
        "created_at": _now(),
        "original_url": _url(original_path),
        "segmentation_url": _url(seg_path),
        "detection_url": _url(det_path),
        "land_cover": seg.percentages,
        "objects": objects,
        "object_counts": counts,
        "confidence": seg.confidence,
        "model_type": model_info["type"],
        "model_accuracy": model_info.get("test_accuracy"),
        "width": w,
        "height": h,
        "location": location,
    }

    # Automated PDF report
    report_path = settings.reports_dir / f"{aid}.pdf"
    try:
        report.generate_report(doc, report_path, original_path, seg_path, det_path)
        doc["report_url"] = _url(report_path)
    except Exception as exc:  # report failure must not fail the whole analysis
        doc["report_url"] = None
        doc["report_error"] = str(exc)

    return doc


def analyze_change(before_bytes: bytes, after_bytes: bytes,
                   name: str, owner: str) -> dict:
    """Change detection between two images -> persisted change document."""
    cid = uuid.uuid4().hex
    before, before_raw = preprocessing.preprocess_pair(before_bytes)
    after, after_raw = preprocessing.preprocess_pair(after_bytes)

    result = change_detection.detect_change(before, after, before_raw=before_raw, after_raw=after_raw)

    from . import landcover_model
    model_info = landcover_model.model_summary() if result.method.startswith("cnn") else {
        "type": "Spectral difference (CIELAB + Otsu)", "test_accuracy": None,
    }

    before_path = settings.uploads_dir / f"{cid}_before.png"
    after_path = settings.uploads_dir / f"{cid}_after.png"
    map_path = settings.masks_dir / f"{cid}_change.png"
    _save_png(result.before_rgb, before_path)
    _save_png(result.after_rgb, after_path)
    _save_png(result.change_map_rgb, map_path)

    return {
        "id": cid,
        "owner": owner,
        "name": name,
        "created_at": _now(),
        "before_url": _url(before_path),
        "after_url": _url(after_path),
        "change_map_url": _url(map_path),
        "changed_percent": result.changed_percent,
        "class_deltas": result.class_deltas,
        "confidence": result.confidence,
        "model_type": model_info["type"],
        "model_accuracy": model_info.get("test_accuracy"),
        "transitions": result.transitions or [],
    }
