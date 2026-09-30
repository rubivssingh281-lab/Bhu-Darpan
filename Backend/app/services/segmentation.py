"""Land-cover segmentation.

Primary path: the EuroSAT-trained CNN labels every pixel, and colour/texture physics
corrects what the CNN cannot know (snow, bare rock, desert, deep water, dense
non-European towns) — see `_hybrid_segment`. Without the CNN, a spectral + texture
per-pixel classifier runs alone, with K-Means-style helpers kept for legacy callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans

from ..config import settings
from .constants import CLASS_COLORS, CLASSES


def classify_rgb(r: float, g: float, b: float) -> str:
    """Map a single RGB colour (0-255) to a land-cover class via HSV-style rules."""
    r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r_, g_, b_), min(r_, g_, b_)
    brightness = mx
    sat = 0.0 if mx == 0 else (mx - mn) / mx

    # 1) Water — blue channel dominant
    if b_ >= g_ and b_ >= r_ and (b_ - min(r_, g_)) > 0.02:
        return "Water"

    # 2) Vegetation — green channel dominant
    if g_ >= r_ and (g_ - b_) > 0.02:
        # Dark, saturated green -> dense forest; brighter/yellower -> cropland
        if brightness < 0.45 and sat > 0.15:
            return "Forest"
        return "Agriculture"

    # 3) Yellow / olive cropland (high R & G, low B)
    if r_ > 0.35 and g_ > 0.30 and (min(r_, g_) - b_) > 0.06 and abs(r_ - g_) < 0.18:
        return "Agriculture"

    # 4) Urban / built-up — grey (low saturation) or reddish rooftops
    if sat < 0.16:
        return "Urban"
    if r_ >= g_ and (r_ - b_) > 0.04 and (r_ - g_) > 0.02:
        return "Urban"

    return "Others"


@dataclass
class SegmentationResult:
    class_map: np.ndarray                 # (H, W) int -> index into CLASSES
    percentages: dict[str, float]         # class -> percent (0-100)
    mask_rgb: np.ndarray                  # (H, W, 3) uint8 colourised mask
    confidence: float                     # 0-100 model / cluster-separation confidence
    method: str = "kmeans"                # "cnn" (supervised) or "kmeans" (fallback)
    cluster_map: np.ndarray = field(repr=False, default=None)  # raw kmeans labels


def _finalize(class_map: np.ndarray, confidence: float, method: str,
              cluster_map: np.ndarray | None = None) -> "SegmentationResult":
    """Build percentages + colourised mask from a class-index map."""
    h, w = class_map.shape
    total = float(h * w)
    class_index = {name: i for i, name in enumerate(CLASSES)}
    percentages = {name: round(100.0 * float(np.count_nonzero(class_map == i)) / total, 2)
                   for name, i in class_index.items()}
    mask_rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for name, i in class_index.items():
        mask_rgb[class_map == i] = CLASS_COLORS[name]
    return SegmentationResult(class_map=class_map, percentages=percentages,
                              mask_rgb=mask_rgb, confidence=confidence,
                              method=method, cluster_map=cluster_map)


def _build_features(arr: np.ndarray) -> np.ndarray:
    """Per-pixel feature vector: RGB + excess-green + blue-index (all ~0-1)."""
    f = arr.reshape(-1, 3).astype(np.float32) / 255.0
    r, g, b = f[:, 0], f[:, 1], f[:, 2]
    exg = np.clip((2 * g - r - b), -1, 1)          # vegetation index
    blue = np.clip((b - (r + g) / 2.0), -1, 1)     # water index
    return np.column_stack([r, g, b, exg * 0.8, blue * 0.8]).astype(np.float32)


def _heterogeneity(arr: np.ndarray) -> np.ndarray:
    """Local colour diversity: the mean per-channel standard deviation in a window.
    Built-up areas mix many materials (roads, varied rooftops, shadows) -> high;
    crop fields are uniform in colour even when row-textured -> low. This is what
    separates 'urban' from 'agriculture' where edge-density alone fails."""
    import cv2
    f = arr.astype(np.float32) / 255.0
    het = np.zeros(f.shape[:2], np.float32)
    for c in range(3):
        ch = f[..., c]
        m = cv2.boxFilter(ch, -1, (21, 21))
        sq = cv2.boxFilter(ch * ch, -1, (21, 21))
        het += np.sqrt(np.maximum(sq - m * m, 0.0))
    return het / 3.0                                # ~0 (uniform) .. ~0.15 (urban)


def _spectral_texture_segment(arr: np.ndarray, cnn_map: np.ndarray | None = None) -> np.ndarray:
    """Per-pixel land-cover classification from colour + vegetation/water indices +
    local texture, producing clean, realistic regions (buildings & roads as built-up,
    fields as agriculture, canopy as forest, water as water). When a CNN class map is
    supplied it only refines the forest-vs-agriculture split on vegetated pixels."""
    import cv2
    h, w = arr.shape[:2]
    f = arr.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    mx = f.max(2)
    mn = f.min(2)
    bright = mx
    sat = (mx - mn) / (mx + 1e-6)
    exg = 2 * g - r - b                              # excess green (vegetation)
    blue = b - (r + g) / 2.0                         # blue index (water)
    het = _heterogeneity(arr)                        # local colour diversity

    idx = {n: i for i, n in enumerate(CLASSES)}
    # Default to Others (bare rock / soil / snow) — NOT agriculture. Natural terrain such
    # as Himalayan mountains and snow must not be painted as cropland or city.
    cls = np.full((h, w), idx["Others"], dtype=np.int32)

    veg = exg > 0.06                                   # any real vegetation (trees/crops)
    forest = veg & (bright < 0.50) & (g >= r)          # dark dense canopy
    agri = veg & (~forest)                             # brighter/greener cropland
    # Snow/ice takes precedence over water: bright + low-saturation (even slightly bluish)
    # is snow, not a water body — otherwise Himalayan snow reads as lakes.
    snow = (bright > 0.68) & (sat < 0.20) & (~veg)     # bright bare / snow -> Others
    water = (blue > 0.04) & (b >= g) & (b >= r) & (bright < 0.68) & (~veg) & (~snow)

    cls[agri] = idx["Agriculture"]
    cls[forest] = idx["Forest"]
    cls[water] = idx["Water"]
    # snow and everything else remain Others (bare) by default.

    # Built-up: STRICT. Requires high colour heterogeneity AND a man-made tone (grey or
    # red rooftop), in a mid-brightness range, and explicitly EXCLUDES natural brown/tan
    # terrain and snow — this is what stopped bare mountains being flagged as a city.
    grayish = sat < 0.20
    redroof = (r - g > 0.06) & (r - b > 0.10) & (bright > 0.35)
    brown_bare = (r >= g) & (g >= b) & (exg < 0.05) & (sat >= 0.12)   # tan/brown natural ground
    # Texture-only urban gate (the EuroSAT CNN over-calls built-up on high-res bare
    # terrain, so it is deliberately NOT used to add urban — only to refine veg below).
    built = ((~water) & (~veg) & (~snow) & (bright > 0.22) & (bright < 0.80)
             & (het > 0.24) & (grayish | redroof) & (~brown_bare))
    built_u8 = built.astype(np.uint8)
    built_u8 = cv2.morphologyEx(built_u8, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    built_u8 = cv2.morphologyEx(built_u8, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    # Keep only sizeable contiguous built-up regions; drop scattered rocky speckle.
    nb, lbl, stats, _ = cv2.connectedComponentsWithStats(built_u8, 8)
    min_urban = 0.0015 * h * w
    for i in range(1, nb):
        if stats[i, cv2.CC_STAT_AREA] >= min_urban:
            cls[lbl == i] = idx["Urban"]

    # CNN refinement: on non-built vegetation/bare pixels the trained model sharpens
    # the forest-vs-agriculture split (never creates built-up or water).
    if cnn_map is not None:
        soft = (cls == idx["Forest"]) | (cls == idx["Agriculture"])
        for c in ("Forest", "Agriculture"):
            cls[soft & (cnn_map == idx[c])] = idx[c]

    cls = cv2.medianBlur(cls.astype(np.uint8), 5).astype(np.int32)
    return cls


def _big_regions(mask: np.ndarray, min_frac: float) -> np.ndarray:
    """Keep only connected regions covering at least `min_frac` of the image."""
    import cv2
    h, w = mask.shape
    nb, lbl, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    keep = np.zeros(nb, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_frac * h * w
    return keep[lbl]


def _hybrid_segment(arr: np.ndarray, p5: np.ndarray, p10: np.ndarray) -> np.ndarray:
    """CNN-first land cover with physical guards.

    The EuroSAT CNN (98% on held-out tiles) labels every pixel; colour/texture physics
    then corrects the cases it cannot know about, because EuroSAT has no class for them:
      * its water must be smooth and not bright, and its built-up must be textured and not
        next to snow (glaciers and bare rock otherwise read as 'Industrial');
      * snow/ice, grey rock, dune sand and barren (vegetation-free) landscapes -> Others;
      * clearly blue / deep, glass-smooth water the model misses -> Water;
      * dense towns the model under-calls (roof/road density among street trees) -> Urban.
    `arr` is the contrast-enhanced image (for the physical tests); p5/p10 come from the
    CNN run on the unenhanced image. Thresholds were tuned on held-out EuroSAT tiles
    plus hand-labelled J&K/world scenes (see docs/PROJECT_GUIDE.md, section 5.2).
    """
    import cv2
    from .landcover_model import EUROSAT_CLASSES
    idx = {n: i for i, n in enumerate(CLASSES)}
    eu = {n: i for i, n in enumerate(EUROSAT_CLASSES)}
    W, U, A, FO, O = idx["Water"], idx["Urban"], idx["Agriculture"], idx["Forest"], idx["Others"]

    f = arr.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    mx, mn = f.max(2), f.min(2)
    bright = mx
    sat = (mx - mn) / (mx + 1e-6)
    exg = 2 * g - r - b                              # excess green (vegetation)
    blue = b - (r + g) / 2.0                         # blue index (water)
    het = _heterogeneity(arr)                        # local colour diversity

    green = (exg > 0.06) & (g - r > 0.015)           # visibly vegetated pixel
    canopy = (p5[..., FO] > 0.5) & (bright < 0.45)   # dark forest canopy has weak excess-green
    snow = (bright > 0.68) & (sat < 0.12) & ~green
    snow &= cv2.blur(snow.astype(np.float32), (41, 41)) > 0.5      # extensive, not a bright roof
    snow_near = cv2.blur(snow.astype(np.float32), (41, 41)) > 0.03

    cls = p5.argmax(2)
    # guard: the model's water must be a smooth, not-bright, non-snow surface; its built-up
    # must be textured, not vegetated, not snow, and 'Industrial' beside ice is rock
    ind_dom = p10[..., eu["Industrial"]] > (p10[..., eu["Residential"]] + p10[..., eu["Highway"]])
    bad = (((cls == W) & ((het > 0.16) | (bright > 0.65) | snow))
           | ((cls == U) & ((het < 0.04) | (exg > 0.15) | snow | (ind_dom & snow_near))))
    if bad.any():
        q = p5.copy()
        q[..., W] = np.where(bad, -1, q[..., W])
        q[..., U] = np.where(bad, -1, q[..., U])
        cls = np.where(bad, q.argmax(2), cls)

    # physically certain water: clearly blue & glass-smooth, or deep/dark & glass-smooth
    water = ((blue > 0.08) & (b >= g) & (b >= r) & (bright < 0.68) & ~green & ~snow
             & (het < 0.05) & ~canopy)
    pveg = p5[..., FO] + p5[..., A]
    deep = ((bright < 0.20) | ((bright < 0.32) & (pveg < 0.5))) & (het < 0.03) & ~snow
    water |= _big_regions(deep, 0.002)
    cls[water] = W

    # surfaces EuroSAT has no class for -> Others: grey rock, dune sand, snow, and non-green
    # ground in a landscape with no vegetation around it (desert / high mountain)
    nongreen_veg = ((cls == A) | (cls == FO)) & ~green & ~canopy
    green_frac = cv2.blur(((green | canopy) & (cls != W)).astype(np.float32), (201, 201))
    bare = nongreen_veg & ((sat < 0.10) | ((sat > 0.40) & (bright > 0.60)) | (green_frac < 0.05))
    cls[bare | snow] = O

    # dense built-up the model under-calls (non-European towns): urban fabric is a density
    # of roofs/roads among street trees, so it is decided over a neighbourhood
    grayish = sat < 0.20
    redroof = (r - g > 0.06) & (r - b > 0.10) & (bright > 0.35)
    brown_bare = (r >= g) & (g >= b) & (exg < 0.05) & (sat >= 0.12)
    man = (grayish | redroof) & ~green & ~brown_bare & (bright > 0.22) & (bright < 0.80) & ~snow
    support = p10[..., eu["Residential"]] + p10[..., eu["Highway"]] + p10[..., eu["Industrial"]]
    built = ((cv2.blur(man.astype(np.float32), (31, 31)) > 0.30) & (het > 0.12)
             & (cv2.blur(support.astype(np.float32), (31, 31)) > 0.10) & ~snow_near & (cls != W))
    built = cv2.morphologyEx(built.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(bool)
    cls[_big_regions(built, 0.0015) & ~water] = U

    return cv2.medianBlur(cls.astype(np.uint8), 5).astype(np.int32)


def segment(arr: np.ndarray, n_clusters: int | None = None,
            raw: np.ndarray | None = None) -> SegmentationResult:
    """Land-cover segmentation.

    With the EuroSAT CNN available: CNN-first hybrid (`_hybrid_segment`). Pass `raw`, the
    decoded image *before* contrast enhancement, so the CNN sees its training domain;
    `arr` (enhanced) drives the physical colour/texture tests. Without the CNN, the
    spectral + texture classifier runs alone.
    """
    from . import landcover_model
    if landcover_model.available():
        cnn_in = raw if raw is not None and raw.shape[:2] == arr.shape[:2] else arr
        pred = landcover_model.predict_proba(cnn_in)
        if pred is not None:
            p5, p10, conf = pred
            class_map = _hybrid_segment(arr, p5, p10)
            return _finalize(class_map, conf, method="cnn")

    # No CNN: use the same spectral + texture classifier (no learned prior).
    class_map = _spectral_texture_segment(arr, cnn_map=None)
    # Confidence proxy: share of pixels that fell into a decisive (non-Others) class.
    decisive = float(np.count_nonzero(class_map != CLASSES.index("Others"))) / class_map.size
    confidence = round(100.0 * (0.6 + 0.35 * decisive), 1)
    return _finalize(class_map, confidence, method="texture")
