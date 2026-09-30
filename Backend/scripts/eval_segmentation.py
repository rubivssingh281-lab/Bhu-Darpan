"""Evaluate the land-cover segmentation *pipeline* (not just the CNN) and write
models/segmentation_eval.json.

Two complementary tests:

(A) EuroSAT held-out test tiles (the same seed-42 stratified split the CNN is scored on)
    run through the full app path: each 64x64 tile is mirror-tiled into a 128x128 block
    (so sliding windows never mix two tiles), blocks are assembled into 768x768 mosaics,
    enhanced exactly as uploads are, segmented, and the majority class of each block's
    centre 64x64 is compared with the grouped label.

(B) Hand-labelled probe boxes on the real scenes in test_images/ (lake water, city
    blocks, riverbeds, rock, snow...) plus whole-scene composition checks (e.g. "the
    Sahara scene must be >=85% bare", "the open-sea scene must be >=80% water").
    EuroSAT has no bare/snow/desert class, so (B) is what catches hallucinated farmland
    or cities on mountains and deserts.

Run from Backend/:  python scripts/eval_segmentation.py [--limit N]
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # Backend/
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

import numpy as np
from PIL import Image

from app.services import landcover_model as lm
from app.services import preprocessing, segmentation
from app.services.constants import CLASSES

IDX = {n: i for i, n in enumerate(CLASSES)}
TEST_IMAGES = BASE.parent / "test_images"
OUT = BASE / "models" / "segmentation_eval.json"

# (x0, y0, x1, y1) as image fractions -> accepted classes
PROBES = {
    "dal_lake_srinagar": [((0.45, 0.25, 0.65, 0.45), {"Water"}), ((0.42, 0.66, 0.60, 0.80), {"Water"}),
                          ((0.00, 0.00, 0.18, 0.30), {"Urban"}), ((0.00, 0.66, 0.14, 0.85), {"Urban"}),
                          ((0.82, 0.30, 1.00, 0.60), {"Forest", "Agriculture", "Others"})],
    "jammu_city": [((0.02, 0.10, 0.28, 0.45), {"Urban"}), ((0.78, 0.72, 0.98, 0.98), {"Urban"}),
                   ((0.62, 0.12, 0.69, 0.32), {"Others", "Water"}),
                   ((0.74, 0.34, 0.86, 0.48), {"Forest", "Agriculture"})],
    "world_water_reservoir": [((0.40, 0.08, 0.55, 0.25), {"Water"}), ((0.02, 0.30, 0.15, 0.42), {"Water"}),
                              ((0.58, 0.55, 0.75, 0.80), {"Others"}), ((0.78, 0.02, 0.98, 0.20), {"Others"})],
    "world_flood_venice": [((0.05, 0.62, 0.25, 0.88), {"Water"}), ((0.36, 0.05, 0.55, 0.20), {"Water"}),
                           ((0.82, 0.70, 0.98, 0.95), {"Water"}), ((0.36, 0.41, 0.52, 0.50), {"Urban"})],
    "world_water_coast": [((0.05, 0.05, 0.60, 0.95), {"Water"}), ((0.74, 0.40, 0.83, 0.60), {"Water"}),
                          ((0.87, 0.18, 0.96, 0.30), {"Urban"})],
    "world_flood_delta": [((0.64, 0.85, 0.76, 0.95), {"Water"}),
                          ((0.05, 0.05, 0.45, 0.25), {"Forest", "Agriculture"}),
                          ((0.55, 0.10, 0.85, 0.40), {"Forest", "Agriculture"})],
    "world_snow_alps": [((0.55, 0.18, 0.75, 0.30), {"Others"}), ((0.10, 0.62, 0.28, 0.74), {"Others"}),
                        ((0.00, 0.20, 0.18, 0.35), {"Forest", "Agriculture", "Others"})],
    "flood_scene": [((0.35, 0.60, 0.65, 0.72), {"Water"}), ((0.03, 0.03, 0.25, 0.25), {"Forest", "Agriculture"})],
    "wildfire_scene": [((0.40, 0.28, 0.60, 0.40), {"Others"}), ((0.40, 0.60, 0.60, 0.70), {"Others"}),
                       ((0.03, 0.03, 0.20, 0.20), {"Forest", "Agriculture"})],
}
# whole-scene composition checks: class -> (min %, max %)
COMPOSITION = {
    "world_drought_sahara": {"Others": (85, 100), "Urban": (0, 2), "Water": (0, 2)},
    "world_drought_thar": {"Others": (60, 100), "Urban": (0, 3), "Water": (0, 3)},
    "world_snow_everest": {"Others": (70, 100), "Urban": (0, 3), "Water": (0, 5)},
    "world_snow_karakoram": {"Others": (60, 100), "Urban": (0, 3), "Water": (0, 5)},
    "world_snow_alps": {"Urban": (0, 3)},
    "wular_lake": {"Urban": (0, 5)},
    "jammu_city": {"Urban": (35, 100)},
    "dal_lake_srinagar": {"Water": (15, 100), "Urban": (15, 100)},
    "world_water_coast": {"Water": (80, 100)},
    "world_flood_venice": {"Water": (55, 100)},
    "world_water_reservoir": {"Water": (25, 100)},
    "wildfire_scene": {"Urban": (0, 3)},
}


def methods(arr: np.ndarray, raw: np.ndarray) -> dict[str, np.ndarray]:
    """arr = enhanced (as the app displays / indexes it); raw = unenhanced (CNN input)."""
    p5, _, _ = lm.predict_proba(raw)
    return {"cnn_only": p5.argmax(2).astype(np.int32),
            "pipeline": segmentation.segment(arr, raw=raw).class_map}


def eval_eurosat(limit: int | None) -> dict:
    from torchvision.datasets import EuroSAT
    from train_landcover import stratified_split
    ds = EuroSAT(root=str(BASE / "data"), download=False)
    y = np.asarray(ds.targets)
    _, _, te = stratified_split(y)
    te = np.random.default_rng(0).permutation(te)
    if limit:
        te = te[:limit]
    to_app = np.array([IDX[lm.EUROSAT_TO_APP[c]] for c in lm.EUROSAT_CLASSES])
    G = 6
    n = (len(te) // (G * G)) * G * G
    conf = {}
    for m0 in range(0, n, G * G):
        ids = te[m0:m0 + G * G]
        blocks = []
        for i in ids:
            t = np.asarray(ds[i][0].convert("RGB").resize((64, 64)))
            blocks.append(np.vstack([np.hstack([t, t[:, ::-1]]), np.hstack([t[::-1], t[::-1, ::-1]])]))
        mosaic = np.vstack([np.hstack(blocks[r * G:(r + 1) * G]) for r in range(G)])
        buf = io.BytesIO()
        Image.fromarray(mosaic).save(buf, format="PNG")
        for k, cm in methods(*preprocessing.preprocess_pair(buf.getvalue())).items():
            c = conf.setdefault(k, np.zeros((5, 5), int))
            for j, i in enumerate(ids):
                ry, rx = divmod(j, G)
                cell = cm[ry * 128 + 32:ry * 128 + 96, rx * 128 + 32:rx * 128 + 96]
                c[to_app[y[i]], np.bincount(cell.ravel(), minlength=5).argmax()] += 1
    out = {"n_tiles": int(n)}
    for k, c in conf.items():
        out[k] = {"grouped_accuracy_pct": round(100 * np.trace(c) / c.sum(), 2),
                  "recall_pct": {CLASSES[i]: round(100 * c[i, i] / max(1, c[i].sum()), 1) for i in range(4)},
                  "confusion": c.tolist()}
    return out


def eval_scenes() -> dict:
    probe, comp, fails = {}, {}, {}
    for fp in sorted(TEST_IMAGES.glob("*.jpg")):
        name = fp.stem
        if name not in PROBES and name not in COMPOSITION:
            continue
        for k, cm in methods(*preprocessing.preprocess_pair(fp.read_bytes())).items():
            h, w = cm.shape
            for (x0, y0, x1, y1), acc in PROBES.get(name, []):
                sub = cm[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
                probe.setdefault(k, []).append(float(np.isin(sub, [IDX[c] for c in acc]).mean()))
            pct = {c: 100 * float((cm == i).mean()) for c, i in IDX.items()}
            for c, (lo, hi) in COMPOSITION.get(name, {}).items():
                ok = lo <= pct[c] <= hi
                comp.setdefault(k, []).append(ok)
                if not ok:
                    fails.setdefault(k, []).append(f"{name}: {c} {pct[c]:.1f}% (want {lo}-{hi}%)")
    return {k: {"probe_pixel_accuracy_pct": round(100 * float(np.mean(v)), 2), "n_probes": len(v),
                "composition_pass": f"{sum(comp[k])}/{len(comp[k])}", "composition_fails": fails.get(k, [])}
            for k, v in probe.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="evaluate only the first N EuroSAT test tiles")
    a = ap.parse_args()
    if not lm.available():
        sys.exit("land-cover CNN not available")
    t0 = time.time()
    res = {"eurosat_pipeline": eval_eurosat(a.limit), "real_scenes": eval_scenes(),
           "model": lm.model_summary(), "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "seconds": round(time.time() - t0)}
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    for k in ("cnn_only", "pipeline"):
        e, s = res["eurosat_pipeline"][k], res["real_scenes"][k]
        print(f"{k:9s} EuroSAT pipeline {e['grouped_accuracy_pct']:6.2f}% | real-scene probes "
              f"{s['probe_pixel_accuracy_pct']:6.2f}% | composition {s['composition_pass']}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
