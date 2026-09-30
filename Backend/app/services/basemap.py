"""Fetch a 'before' baseline image from the Esri World Imagery basemap.

The Disaster module can auto-fetch a pre-event baseline for a coordinate straight
from the same Esri World Imagery service the Leaflet map renders. That imagery is a
few years old, so it serves as a natural 'before' scene for change-based confirmation
of a freshly-uploaded post-event image — the user only has to supply lat/lon.
"""
from __future__ import annotations

import math

import requests

# Same service the front-end Leaflet map uses (World_Imagery), via its export endpoint.
_EXPORT = ("https://services.arcgisonline.com/arcgis/rest/services/"
           "World_Imagery/MapServer/export")


def fetch_baseline(lat: float, lon: float, half_km: float = 1.5,
                   size: int = 768, timeout: float = 25.0) -> bytes | None:
    """Return JPEG bytes of the Esri basemap around (lat, lon), or None on failure.

    `half_km` is half the box side in kilometres (so the scene spans 2·half_km across);
    `size` is the output image edge in pixels.
    """
    try:
        half_km = max(0.2, min(float(half_km), 25.0))
        d_lat = half_km / 111.0
        d_lon = half_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
        bbox = f"{lon - d_lon},{lat - d_lat},{lon + d_lon},{lat + d_lat}"
        params = {
            "bbox": bbox, "bboxSR": "4326", "imageSR": "4326",
            "size": f"{size},{size}", "format": "jpg", "f": "image",
        }
        r = requests.get(_EXPORT, params=params, timeout=timeout)
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image") and r.content:
            return r.content
    except Exception:
        pass
    return None
