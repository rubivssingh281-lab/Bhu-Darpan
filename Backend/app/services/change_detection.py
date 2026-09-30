"""Change detection between two co-located satellite images (before vs after).

Computes a perceptual difference in CIELAB space, thresholds it (Otsu) into a
change mask, and reports the changed area percentage plus per-class area deltas
derived from segmenting both epochs. Produces a red/green change overlay.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .constants import CLASSES
from .segmentation import segment


@dataclass
class ChangeResult:
    change_map_rgb: np.ndarray
    changed_percent: float
    class_deltas: dict[str, float]
    confidence: float
    before_rgb: np.ndarray
    after_rgb: np.ndarray
    method: str = "spectral"              # "cnn+spectral" or "spectral"
    transitions: list = None              # top land-cover transitions [{from,to,pct}]


def detect_change(before: np.ndarray, after: np.ndarray,
                  before_raw: np.ndarray | None = None, after_raw: np.ndarray | None = None) -> ChangeResult:
    """Detect *genuine* land-cover conversions between two co-located epochs.

    Change = a pixel whose land-cover **type actually converted** (e.g. Water→bare
    [water loss], Vegetation→Urban [development], Vegetation→Water [flooding]),
    confirmed by a real spectral difference. Forest↔Agriculture is treated as one
    'vegetation' super-class so seasonal greening / crop-cycle colour shifts are
    NOT reported as change — the per-class area deltas still surface those.
    `before_raw` / `after_raw` are the unenhanced images for the CNN (optional).
    """
    h, w = before.shape[:2]
    if after.shape[:2] != (h, w):
        after = cv2.resize(after, (w, h), interpolation=cv2.INTER_AREA)
        if after_raw is not None:
            after_raw = cv2.resize(after_raw, (w, h), interpolation=cv2.INTER_AREA)

    idx = {n: i for i, n in enumerate(CLASSES)}
    seg_b = segment(before, raw=before_raw)
    seg_a = segment(after, raw=after_raw)
    class_deltas = {c: round(seg_a.percentages[c] - seg_b.percentages[c], 2) for c in CLASSES}

    # Super-class map: Forest + Agriculture -> one 'vegetation' code, so crop/forest
    # seasonal swaps don't count; Water / Urban / Others stay distinct.
    def _superc(cm):
        s = cm.copy()
        s[(cm == idx["Forest"]) | (cm == idx["Agriculture"])] = idx["Forest"]
        return s

    structural = _superc(seg_a.class_map) != _superc(seg_b.class_map)

    # Confirm with a real perceptual difference (removes classifier flicker at edges)
    lab_b = cv2.cvtColor(before, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab_a = cv2.cvtColor(after, cv2.COLOR_RGB2LAB).astype(np.float32)
    diff = np.sqrt(np.sum((lab_a - lab_b) ** 2, axis=2))
    spectral_sig = diff > 14.0

    change_bool = structural & spectral_sig
    cm_u8 = cv2.morphologyEx(change_bool.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    change_bool = cm_u8 > 0

    changed_percent = round(100.0 * float(np.count_nonzero(change_bool)) / (h * w), 2)

    if seg_a.method == "cnn":
        method = "cnn+semantic"
        confidence = round((seg_a.confidence + seg_b.confidence) / 2.0, 1)
    else:
        method = "semantic"
        confidence = round((seg_a.confidence + seg_b.confidence) / 2.0, 1)

    # Red where changed, green where unchanged, blended over the 'after' image
    tint = np.zeros_like(after)
    tint[change_bool] = (229, 57, 53)      # changed -> red
    tint[~change_bool] = (46, 125, 50)     # unchanged -> green
    change_map_rgb = cv2.addWeighted(after.copy(), 0.6, tint, 0.4, 0)

    # Real conversions (from-class -> to-class) among the changed pixels
    transitions = []
    if change_bool.any():
        tot = int(np.count_nonzero(change_bool))
        fb = seg_b.class_map[change_bool]
        fa = seg_a.class_map[change_bool]
        pair_counts = {}
        for bi, ai in zip(fb, fa):
            if bi == ai:
                continue
            pair_counts[(int(bi), int(ai))] = pair_counts.get((int(bi), int(ai)), 0) + 1
        for (fi, ti), cnt in sorted(pair_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]:
            transitions.append({
                "from": CLASSES[fi], "to": CLASSES[ti],
                "pct": round(100.0 * cnt / tot, 1),
            })

    return ChangeResult(
        change_map_rgb=change_map_rgb,
        changed_percent=changed_percent,
        class_deltas=class_deltas,
        confidence=confidence,
        before_rgb=before,
        after_rgb=after,
        method=method,
        transitions=transitions,
    )
