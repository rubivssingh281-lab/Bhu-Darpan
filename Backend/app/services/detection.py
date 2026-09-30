"""Object detection on satellite imagery.

Detects key features named in the project spec — Buildings, Roads, Water Bodies,
Vegetation and Farmland — using connected-component analysis on the land-cover
segmentation plus Hough-line detection for roads. Each detection carries a bounding
box and a computed confidence, and is drawn onto an annotated overlay image.
"""
from __future__ import annotations

import cv2
import numpy as np

from .constants import CLASSES

_CLASS_IDX = {name: i for i, name in enumerate(CLASSES)}

# Draw colours (RGB) per detected object type
_DRAW = {
    "Building": (229, 57, 53),
    "Road": (255, 179, 0),
    "Water Body": (21, 101, 192),
    "Vegetation": (46, 125, 50),
    "Farmland": (176, 190, 40),
}


def _mask_for(class_map: np.ndarray, name: str) -> np.ndarray:
    return (class_map == _CLASS_IDX[name]).astype(np.uint8) * 255


def _line_kernels(length: int = 27):
    """Line-shaped structuring elements at 0/45/90/135 degrees for road morphology."""
    e = np.eye(length, dtype=np.uint8)
    return [np.ones((1, length), np.uint8), np.ones((length, 1), np.uint8),
            e, np.fliplr(e)]


def _blob_boxes(mask: np.ndarray, min_area: float, max_area: float,
                aspect_range=(0.0, 1e9), limit: int = 20):
    """Return [(x, y, w, h, purity)] for connected components passing filters."""
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < min_area or area > max_area:
            continue
        aspect = w / float(h) if h else 0
        if not (aspect_range[0] <= aspect <= aspect_range[1]):
            continue
        box_area = float(w * h) or 1.0
        purity = float(area) / box_area
        out.append((int(x), int(y), int(w), int(h), purity))
    out.sort(key=lambda t: t[2] * t[3], reverse=True)
    return out[:limit]


def detect_objects(arr: np.ndarray, class_map: np.ndarray):
    """Run detection; return (objects, counts, annotated_overlay_rgb)."""
    h, w = class_map.shape
    total = float(h * w)
    diag = float(np.hypot(h, w))
    objects: list[dict] = []

    f = arr.astype(np.float32) / 255.0
    bright = f.max(2)
    sat = (f.max(2) - f.min(2)) / (f.max(2) + 1e-6)

    # --- Buildings: distinct rooftops (bright/compact) inside built-up areas -
    building_mask = ((class_map == _CLASS_IDX["Urban"]) & (bright > 0.48)).astype(np.uint8) * 255
    building_mask = cv2.morphologyEx(building_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    for (x, y, bw, bh, purity) in _blob_boxes(
        building_mask, min_area=0.0009 * total, max_area=0.02 * total,
        aspect_range=(0.45, 2.4), limit=15,
    ):
        if purity < 0.55:                    # reject sprawling, non-compact blobs
            continue
        objects.append({
            "label": "Building", "bbox": [x, y, bw, bh],
            "confidence": round(min(98.0, 58 + 40 * purity), 1),
        })

    # --- Water bodies -----------------------------------------------------
    for (x, y, bw, bh, purity) in _blob_boxes(
        _mask_for(class_map, "Water"), min_area=0.004 * total, max_area=total, limit=6,
    ):
        objects.append({"label": "Water Body", "bbox": [x, y, bw, bh],
                        "confidence": round(min(99.0, 60 + 39 * purity), 1)})

    # --- Vegetation patches (forest / canopy) -----------------------------
    for (x, y, bw, bh, purity) in _blob_boxes(
        _mask_for(class_map, "Forest"), min_area=0.008 * total, max_area=total, limit=8,
    ):
        objects.append({"label": "Vegetation", "bbox": [x, y, bw, bh],
                        "confidence": round(min(99.0, 58 + 41 * purity), 1)})

    # --- Farmland (agriculture) -------------------------------------------
    for (x, y, bw, bh, purity) in _blob_boxes(
        _mask_for(class_map, "Agriculture"), min_area=0.01 * total, max_area=total, limit=6,
    ):
        objects.append({"label": "Farmland", "bbox": [x, y, bw, bh],
                        "confidence": round(min(99.0, 56 + 43 * purity), 1)})

    # --- Roads: road NETWORK via directional (line-shaped) morphology -------
    # Roads are elongated grey/asphalt structures. Opening a grey-surface mask with
    # line elements at several angles keeps long thin roads and drops compact blobs;
    # subtracting a square-opening removes solid built-up areas. Robust on dense
    # cities where Hough lines spam spurious diagonals.
    grayf = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    road_cand = ((grayf > 0.15) & (grayf < 0.52) & (sat < 0.22)).astype(np.uint8)
    acc = np.zeros_like(road_cand)
    for k in _line_kernels(27):
        acc = np.maximum(acc, cv2.morphologyEx(road_cand, cv2.MORPH_OPEN, k))
    blob = cv2.morphologyEx(road_cand, cv2.MORPH_OPEN, np.ones((27, 27), np.uint8))
    road_mask = ((acc > 0) & (blob == 0)).astype(np.uint8)
    road_mask = cv2.morphologyEx(road_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    road_mask = cv2.morphologyEx(road_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    nr, _, stats, _ = cv2.connectedComponentsWithStats(road_mask, 8)
    for i in range(1, nr):
        x, y, bw, bh, area = stats[i]
        if area < 0.0003 * total:          # ignore tiny fragments
            continue
        elong = max(bw, bh) / (min(bw, bh) + 1e-6)
        if elong < 1.8:                    # roads are elongated, not blobby
            continue
        objects.append({"label": "Road", "bbox": [int(x), int(y), int(bw), int(bh)],
                        "confidence": round(min(96.0, 60 + area / total * 400), 1)})

    # --- Annotated overlay -------------------------------------------------
    overlay = arr.copy()
    ys, xs = np.where(road_mask > 0)       # tint the extracted road network
    if len(ys):
        overlay[ys, xs] = (0.35 * overlay[ys, xs] + 0.65 * np.array(_DRAW["Road"])).astype(np.uint8)
    labelled = set()
    for obj in objects:
        if obj["label"] == "Road":
            continue
        color = _DRAW.get(obj["label"], (255, 255, 255))
        x, y, bw, bh = obj["bbox"]
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), color, 2)
        if obj["label"] not in labelled:   # label each type once (less clutter)
            cv2.putText(overlay, obj["label"], (x, max(12, y - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
            labelled.add(obj["label"])

    counts: dict[str, int] = {}
    for obj in objects:
        counts[obj["label"]] = counts.get(obj["label"], 0) + 1

    return objects, counts, overlay
