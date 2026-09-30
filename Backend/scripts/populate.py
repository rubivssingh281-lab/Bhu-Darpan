"""Populate the RUNNING server with real analyses over HTTP (visual demo data)."""
import io
import httpx
import numpy as np
from PIL import Image

BASE = "http://127.0.0.1:8000"


def scene(seed, urban_scale=1.0, forest_scale=1.0):
    rng = np.random.default_rng(seed)
    h, w = 560, 820
    img = np.zeros((h, w, 3), np.uint8)
    img[:, :] = (150, 150, 95) + rng.integers(-18, 18, (h, w, 3))
    yy, xx = np.mgrid[0:h, 0:w]
    forest = ((xx - 180) ** 2 / (220 * forest_scale) ** 2 + (yy - 150) ** 2 / 150 ** 2) < 1
    img[forest] = (48, 92, 40) + rng.integers(-14, 14, (int(forest.sum()), 3))
    for x in range(w):
        cy = int(360 + 70 * np.sin(x / 90.0) + 25 * np.sin(x / 23.0))
        img[max(0, cy - 14):cy + 14, x] = (34, 74, 150)
    lake = ((xx - 660) ** 2 / 90 ** 2 + (yy - 160) ** 2 / 60 ** 2) < 1
    img[lake] = (30, 78, 158)
    uw = min(int(280 * urban_scale), 300)
    img[430:540, 520:520 + uw] = (145, 143, 140) + rng.integers(-12, 12, (110, uw, 3))
    for by in range(440, 535, 22):
        for bx in range(528, 520 + uw - 20, 30):
            img[by:by + 15, bx:bx + 22] = (185, 95, 82)
    img[300:305, :] = (120, 118, 115)
    img[:, 470:475] = (120, 118, 115)
    buf = io.BytesIO()
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(buf, "PNG")
    return buf.getvalue()


with httpx.Client(base_url=BASE, timeout=60) as c:
    tok = c.post("/api/auth/login", json={"email": "demo@bhudarpan.ai", "password": "demo1234"}).json()["token"]
    H = {"Authorization": f"Bearer {tok}"}

    scenes = [
        ("Ghaziabad_Sector_2026", 28.67, 77.45, 6, scene(1)),
        ("Yamuna_Floodplain_2026", 28.55, 77.30, 7, scene(2, urban_scale=0.4, forest_scale=1.3)),
        ("Industrial_Belt_2026", 28.70, 77.50, 6, scene(3, urban_scale=1.7, forest_scale=0.6)),
    ]
    for name, lat, lon, k, data in scenes:
        r = c.post("/api/analysis", headers=H,
                   files={"file": (f"{name}.png", data, "image/png")},
                   data={"name": name, "lat": str(lat), "lon": str(lon), "clusters": str(k)})
        d = r.json()
        print(f"{name}: {r.status_code} | conf {d.get('confidence')} | {d.get('object_counts')}")

    # a change-detection pair (forest shrinks, urban grows)
    r = c.post("/api/change", headers=H,
               files={"before": ("before.png", scene(5, urban_scale=0.5, forest_scale=1.4), "image/png"),
                      "after": ("after.png", scene(5, urban_scale=1.8, forest_scale=0.5), "image/png")},
               data={"name": "Urban_Expansion_2020_2026"})
    print("change:", r.status_code, "| changed %:", r.json().get("changed_percent"))

print("done")
