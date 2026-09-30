"""Disaster detection & authority-alerting for the satellite module.

Analyses an uploaded satellite scene (optionally with a pre-event baseline) and flags
likely disasters — flood, drought/vegetation-loss, wildfire/burn-scar, snow/avalanche,
landslide — with an affected-area estimate, severity, a built-up **exposure** proxy and a
copy-ready authority alert.

Backbone: the project's EuroSAT land-cover CNN + hybrid segmenter (accuracy read from
models/landcover_metrics.json) supplies Water / vegetation / built-up / bare fractions;
physically-grounded RGB indices refine the call.
This is an operational, explainable triage layer — NOT a trained trapped-victim detector.
Detecting individual people from satellite pixels is infeasible at these resolutions, so the
"exposure" output is a population/structure proxy over the impact zone, flagged accordingly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
from PIL import Image

from ..config import settings
from . import landcover_model, preprocessing, segmentation

# affected-area (% of scene) -> severity band
_SEVERITY = [(35, "Severe"), (15, "High"), (5, "Moderate"), (0, "Low")]


def _severity(pct: float) -> str:
    for thr, label in _SEVERITY:
        if pct >= thr:
            return label
    return "Low"


def _channels(arr: np.ndarray):
    f = arr.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    bright = (r + g + b) / 3.0
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) / (mx + 1e-6)
    exg = 2 * g - r - b                      # vegetation vigour (green excess)
    return r, g, b, bright, sat, exg


def _index_masks(arr: np.ndarray):
    """Physically-grounded RGB index masks (each a boolean HxW)."""
    r, g, b, bright, sat, exg = _channels(arr)
    veg = exg > 0.08                                   # healthy vegetation
    # bright, low-saturation → snow/cloud (0.72 keeps shaded alpine snow; the brightest
    # non-snow test scenes — city roofs, dry riverbeds — stay under 10% of the frame)
    snow = (bright > 0.72) & (sat < 0.18)
    # Active fire / flame front: intense, near-saturated red that dominates BOTH other
    # channels. Deserts/orange sand are only mildly red (r−g small), so require a large
    # red-over-green gap to avoid flagging sand or terracotta rooftops as fire.
    fire = (r > 0.68) & ((r - g) > 0.28) & ((r - b) > 0.42) & (sat > 0.45)
    # Smoke plume: desaturated grey, mid/high brightness (rises off an active fire)
    smoke = (sat < 0.12) & (bright > 0.45) & (bright < 0.90) & (~fire) & (~snow)
    burn = (r > g + 0.04) & (exg < -0.02) & (bright < 0.55) & (~fire)   # dark char / burn scar
    bare = (r > g) & (g > b) & (exg < 0.04) & (bright > 0.30) & (~snow)  # brown bare soil
    # Open water (RGB, beyond the blue-only segmentation): clear-blue, deep/dark still
    # water, and grey turbid/muddy floodwater — the signatures a real flood shows.
    blue_water = (b >= r + 0.015) & (b + 0.01 >= g) & (bright < 0.62) & (bright > 0.06)
    dark_water = (bright < 0.26) & (sat < 0.35) & (exg < 0.06)            # deep / shadowed water
    grey_turbid = (sat < 0.14) & (bright > 0.18) & (bright < 0.52) & (exg < 0.05) & (np.abs(r - b) < 0.06)
    water = (blue_water | dark_water | grey_turbid) & (~snow) & (~fire)
    return {"veg": veg, "snow": snow, "burn": burn, "bare": bare,
            "fire": fire, "smoke": smoke, "water": water}


def _model_basis() -> str:
    """One-line model citation for the alert, read from the live metrics file."""
    m = landcover_model.metrics() or {}
    acc = m.get("test_accuracy_pct")
    return f"EuroSAT land-cover CNN ({acc}% held-out test)" if acc else "EuroSAT land-cover CNN"


def _pct(mask: np.ndarray) -> float:
    return round(100.0 * float(np.count_nonzero(mask)) / mask.size, 1)


def _analyse_scene(arr: np.ndarray, raw: np.ndarray | None = None) -> dict:
    seg = segmentation.segment(arr, raw=raw)
    p = seg.percentages
    idx = _index_masks(arr)
    water_rgb = _pct(idx["water"])
    return {
        "seg": seg, "pct": p, "idx": idx,
        # blend the segmentation Water class with the RGB water index so green/turbid/
        # dark flood water (which the blue-tuned segmenter misses) still registers
        "water": round(max(p.get("Water", 0.0), water_rgb), 1),
        "water_rgb": water_rgb,
        "veg": p.get("Forest", 0.0) + p.get("Agriculture", 0.0),
        "urban": p.get("Urban", 0.0),
        "others": p.get("Others", 0.0),
        "snow_pct": _pct(idx["snow"]),
        "burn_pct": _pct(idx["burn"]),
        "bare_pct": _pct(idx["bare"]),
        "fire_pct": _pct(idx["fire"]),
        "smoke_pct": _pct(idx["smoke"]),
        "confidence": seg.confidence,
    }


def _save_overlay(arr: np.ndarray, impact: np.ndarray, colour) -> str:
    """Dim the scene and paint the impact mask; return a /storage URL."""
    did = uuid.uuid4().hex
    base = (arr.astype(np.float32) * 0.55).astype(np.uint8)
    out = base.copy()
    out[impact] = colour
    path = settings.masks_dir / f"{did}_disaster.png"
    Image.fromarray(out).save(path, format="PNG")
    return f"/storage/masks/{path.name}"


def _load_rgb(data: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Decode to (enhanced, raw) RGB uint8 arrays — raw is the unenhanced image the CNN
    expects; fall back to a false-colour preview for multispectral GeoTIFFs that PIL
    can't open (float / 16-bit / >3-band)."""
    try:
        return preprocessing.preprocess_pair(data)
    except Exception:
        pass
    try:
        from . import multispectral
        if multispectral.available():
            prev = multispectral.preview_rgb(data)
            if prev is not None:
                raw = preprocessing.resize_max(prev)
                return preprocessing.enhance(raw), raw
    except Exception:
        pass
    raise ValueError("Could not decode image. For multispectral GeoTIFFs, install tifffile or rasterio.")


def detect(data: bytes, before: bytes | None = None,
           region_name: str = "Jammu & Kashmir", location: dict | None = None) -> dict:
    arr, raw = _load_rgb(data)
    cur = _analyse_scene(arr, raw)
    detections: list[dict] = []
    impact = np.zeros(arr.shape[:2], dtype=bool)
    overlay_colour = (21, 101, 192)

    mode = "change" if before is not None else "single"

    # ---- single-scene absolute detection — ALWAYS runs, so a disaster visible in
    #      the uploaded scene is caught even when the baseline is from a different
    #      location or the two frames are not perfectly co-registered. -------------
    if cur["fire_pct"] > 0.10:
        conf = float(np.clip(0.60 + cur["fire_pct"] / 5.0, 0, 0.97))
        smk = f", with a smoke plume over ~{cur['smoke_pct']}%" if cur["smoke_pct"] > 3 else ""
        detections.append({"type": "Active fire / wildfire", "confidence": round(conf, 2),
                           "affected_area_pct": cur["fire_pct"],
                           "evidence": f"Bright orange-red flame hotspots over {cur['fire_pct']}% of the scene — active fire front{smk}."})
        impact |= cur["idx"]["fire"] | (cur["idx"]["smoke"] if cur["smoke_pct"] > 3 else cur["idx"]["fire"])
    standing_water = np.zeros(arr.shape[:2], dtype=bool)
    if cur["water"] > 18:
        conf = float(np.clip(0.35 + cur["water"] / 90.0, 0, 0.9))
        detections.append({"type": "Flood / standing water", "confidence": round(conf, 2),
                           "affected_area_pct": round(cur["water"], 1),
                           "evidence": f"Open water covers {cur['water']:.1f}% of the scene (supply a matching pre-event image to rule out a permanent water body)."})
        standing_water = (cur["seg"].class_map == segmentation.CLASSES.index("Water")) | cur["idx"]["water"]
        impact |= standing_water
    if cur["snow_pct"] > 22:
        conf = float(np.clip(0.4 + cur["snow_pct"] / 100.0, 0, 0.92))
        detections.append({"type": "Snow / avalanche terrain", "confidence": round(conf, 2),
                           "affected_area_pct": cur["snow_pct"],
                           "evidence": f"Bright low-saturation (snow/ice) cover {cur['snow_pct']:.1f}% — avalanche-prone if on steep terrain."})
        impact |= cur["idx"]["snow"]
    # bare ground: the brown-soil index, or the segmenter's bare class (pale dune sand is
    # not 'brown' but is bare) when the scene is not snow-covered
    bare_like = max(cur["bare_pct"], cur["others"] if cur["snow_pct"] < 10 else 0.0)
    if cur["veg"] < 16 and cur["water"] < 6 and bare_like > 28:
        conf = float(np.clip(0.35 + (bare_like - 28) / 90.0, 0, 0.88))
        detections.append({"type": "Drought / vegetation stress", "confidence": round(conf, 2),
                           "affected_area_pct": round(bare_like, 1),
                           "evidence": f"Vegetation only {cur['veg']:.1f}% with {bare_like:.1f}% bare/exposed ground — moisture-stressed / arid."})
        impact |= cur["idx"]["bare"] | ((cur["seg"].class_map == segmentation.CLASSES.index("Others")) & ~cur["idx"]["snow"])
    if cur["burn_pct"] > 10:
        conf = float(np.clip(0.3 + cur["burn_pct"] / 60.0, 0, 0.85))
        detections.append({"type": "Wildfire / burn scar", "confidence": round(conf, 2),
                           "affected_area_pct": cur["burn_pct"],
                           "evidence": f"Char/burn signature over {cur['burn_pct']:.1f}% (RGB-indicative — confirm with SWIR/thermal)."})
        impact |= cur["idx"]["burn"]

    # ---- change evidence — ADDED on top when a pre-event baseline is available ---
    if before is not None:
        pre = _analyse_scene(*_load_rgb(before))
        dwater = cur["water"] - pre["water"]
        dveg = cur["veg"] - pre["veg"]
        dbare = cur["bare_pct"] - pre["bare_pct"]
        dburn = cur["burn_pct"] - pre["burn_pct"]
        if pre["water"] > 12 and standing_water.any():
            # the baseline already holds a permanent lake / sea / reservoir, so total water
            # cover is not flood evidence — only a measured rise (below) is
            detections = [d for d in detections if d["type"] != "Flood / standing water"]
            impact &= ~standing_water
        if pre["veg"] < 16 and pre["water"] < 6:
            for d in detections:
                if d["type"].startswith("Drought"):
                    d["evidence"] += " The pre-event baseline is equally arid — a persistent condition, not a new event."
        if dwater > 6:
            conf = float(np.clip(0.5 + dwater / 60.0, 0, 0.97))
            detections.append({"type": "Flood (post-event rise)", "confidence": round(conf, 2),
                               "affected_area_pct": round(dwater, 1),
                               "evidence": f"Open-water cover rose {dwater:+.1f}% vs the pre-event baseline — new inundation."})
            impact |= cur["seg"].class_map == segmentation.CLASSES.index("Water")
        if dveg < -8 and dbare > 4:
            conf = float(np.clip(0.4 + abs(dveg) / 50.0, 0, 0.95))
            detections.append({"type": "Landslide / land loss", "confidence": round(conf, 2),
                               "affected_area_pct": round(abs(dveg), 1),
                               "evidence": f"Vegetation fell {dveg:+.1f}% with bare ground up {dbare:+.1f}% vs baseline — mass-movement or clearing."})
            impact |= cur["idx"]["bare"]
        if dburn > 4 and dveg < -4:
            conf = float(np.clip(0.42 + dburn / 30.0, 0, 0.9))
            detections.append({"type": "Wildfire burn scar (post-event)", "confidence": round(conf, 2),
                               "affected_area_pct": round(dburn, 1),
                               "evidence": f"Char/burn signature up {dburn:+.1f}% with vegetation loss vs baseline (confirm with SWIR)."})
            impact |= cur["idx"]["burn"]

    # keep only the strongest detection per disaster family (avoid near-duplicates)
    def _family(t):
        t = t.lower()
        if "fire" in t and "burn" not in t: return "fire"
        if "burn" in t: return "burn"
        if "flood" in t or "water" in t: return "flood"
        if "landslide" in t or "land loss" in t: return "landslide"
        if "snow" in t or "avalanche" in t: return "snow"
        if "drought" in t or "stress" in t: return "drought"
        return t
    _best: dict = {}
    for d in detections:
        fam = _family(d["type"])
        if fam not in _best or d["confidence"] > _best[fam]["confidence"]:
            _best[fam] = d
    detections = list(_best.values())

    # --- optional multispectral confirmation (NIR/SWIR) — decisive when bands exist ---
    ms_summary = None
    try:
        from . import multispectral
        ms = multispectral.indices(data) if multispectral.available() else None
    except Exception:
        ms = None
    if ms:
        ms_summary = {k: ms[k] for k in
                      ("water_pct", "veg_pct", "burn_pct", "active_fire_pct",
                       "ndwi_mean", "ndvi_mean", "nbr_mean", "note")}
        if ms.get("active_fire_pct", 0) > 1:
            detections.append({"type": "Active fire (SWIR-confirmed)",
                               "confidence": round(min(0.98, 0.65 + ms["active_fire_pct"] / 30.0), 2),
                               "affected_area_pct": ms["active_fire_pct"],
                               "evidence": f"SWIR active-fire anomaly over {ms['active_fire_pct']}% (thermal hot-spot — decisive)."})
        if ms["water_pct"] > 15:
            detections.append({"type": "Flood (NDWI-confirmed)",
                               "confidence": round(min(0.98, 0.6 + ms["water_pct"] / 80.0), 2),
                               "affected_area_pct": ms["water_pct"],
                               "evidence": f"NDWI open-water {ms['water_pct']}% (NIR-based — decisive, not shadow)."})
        if ms["burn_pct"] > 8:
            detections.append({"type": "Wildfire (NBR-confirmed)",
                               "confidence": round(min(0.95, 0.5 + ms["burn_pct"] / 50.0), 2),
                               "affected_area_pct": ms["burn_pct"],
                               "evidence": f"NBR burned-area {ms['burn_pct']}% (SWIR-based — decisive)."})
        if before is not None:
            try:
                dn = multispectral.dnbr(before, data)
                if dn:
                    ms_summary["dnbr"] = dn
            except Exception:
                pass

    # merge multispectral-confirmed detections into their family, keeping the strongest
    _best2: dict = {}
    for d in detections:
        fam = _family(d["type"])
        if fam not in _best2 or d["confidence"] > _best2[fam]["confidence"]:
            _best2[fam] = d
    detections = list(_best2.values())

    detections.sort(key=lambda d: d["confidence"], reverse=True)

    # colour the overlay by the primary (highest-confidence) detection
    _FAM_COL = {"fire": (230, 90, 40), "burn": (230, 90, 40), "flood": (21, 101, 192),
                "landslide": (150, 96, 60), "snow": (120, 200, 230), "drought": (196, 150, 90)}
    if detections:
        overlay_colour = _FAM_COL.get(_family(detections[0]["type"]), overlay_colour)

    affected = round(max([d["affected_area_pct"] for d in detections], default=0.0), 1)
    primary = detections[0]["type"] if detections else "No disaster signature"
    severity = _severity(affected) if detections else "None"
    # An active fire is time-critical even over a small area — never rank it below High.
    if any("fire" in d["type"].lower() for d in detections):
        order = ["None", "Low", "Moderate", "High", "Severe"]
        if order.index(severity) < order.index("High"):
            severity = "High"

    # exposure proxy: built-up cover, and how much of it sits in the impact zone
    urban_idx = cur["seg"].class_map == segmentation.CLASSES.index("Urban")
    exposed = urban_idx & impact
    exposed_pct = _pct(exposed) if impact.any() else 0.0
    exposure = {
        "builtup_pct": round(cur["urban"], 1),
        "builtup_in_impact_pct": exposed_pct,
        "note": ("Built-up/urban cover overlaps the impact zone — structures and population "
                 "likely exposed; prioritise ground verification."
                 if exposed_pct > 0.5 else
                 "Little built-up cover within the impact zone in this scene."),
    }

    overlay_url = _save_overlay(arr, impact, overlay_colour) if impact.any() else None

    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    loc = f" ({location['lat']:.3f}, {location['lon']:.3f})" if location else ""
    if detections:
        top = detections[0]
        alert = (
            f"DISASTER ALERT — {region_name}{loc}\n"
            f"Type: {primary} (confidence {int(top['confidence'] * 100)}%)\n"
            f"Severity: {severity} · Affected area: ~{affected}% of scene\n"
            f"Exposure: built-up cover {exposure['builtup_pct']}%"
            + (f", {exposed_pct}% within impact zone" if exposed_pct > 0.5 else "") + "\n"
            f"Detected: {when}\n"
            f"Recommended: notify J&K SDMA / District Control Room; dispatch assessment team; "
            f"issue local advisory to exposed wards.\n"
            f"Basis: {_model_basis()} + spectral disaster indices — triage aid, verify on ground."
        )
    else:
        alert = (f"NO DISASTER SIGNATURE — {region_name}{loc}\n"
                 f"Scene within normal land-cover ranges as of {when}. No alert issued.")

    return {
        "mode": mode,
        "region": region_name,
        "detected_at": when,
        "primary": primary,
        "severity": severity,
        "affected_area_pct": affected,
        "detections": detections,
        "land_cover": cur["pct"],
        "exposure": exposure,
        "overlay_url": overlay_url,
        "multispectral": ms_summary,
        "authority_alert": alert,
        "backbone": {"model": "EuroSAT land-cover CNN",
                     "test_accuracy_pct": (landcover_model.metrics() or {}).get("test_accuracy_pct"),
                     "confidence_pct": cur["confidence"]},
        "limitations": [
            "Optical RGB only: flood (open water), snow and vegetation loss are reliable; "
            "burn scars and landslides are indicative and best confirmed with SWIR/thermal/SAR.",
            "Single-scene flood may include permanent water bodies — supply a pre-event image for change-based confirmation.",
            "Exposure is a built-up-area proxy, NOT trapped-person detection — individuals are not resolvable at satellite GSD.",
            "Output is decision-support triage; authorities must verify before acting.",
        ],
    }
