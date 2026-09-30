"""Supervised land-cover model (EuroSAT-trained CNN) + patch-based inference.

This replaces the unsupervised K-Means guesswork with a *trained* classifier whose
accuracy is measured on a held-out EuroSAT test split, so every segmentation /
change-detection output is backed by a real, citable number.

The model is a small CNN trained on the EuroSAT RGB benchmark (27,000 Sentinel-2
tiles, 10 land-cover classes). At inference we slide 64x64 windows over the
preprocessed image, classify each with the CNN, and stitch the predictions into a
land-cover map. EuroSAT's 10 classes are grouped into the project's 5 classes
(Forest / Water / Agriculture / Urban / Others).

Torch is an *optional* dependency: if it (or the trained weights) is missing,
`available()` returns False and the pipeline falls back to K-Means. The app never
crashes just because torch isn't installed.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..config import settings
from .constants import CLASSES

try:  # torch is optional — the app must run without it
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH = True
except Exception:  # pragma: no cover - torch not installed
    _TORCH = False

# --------------------------------------------------------------------------- #
# EuroSAT label space and the mapping into the project's 5 land-cover classes
# --------------------------------------------------------------------------- #
# torchvision.datasets.EuroSAT sorts class folders alphabetically:
EUROSAT_CLASSES = [
    "AnnualCrop", "Forest", "HerbaceousVegetation", "Highway", "Industrial",
    "Pasture", "PermanentCrop", "Residential", "River", "SeaLake",
]

# EuroSAT class -> one of CLASSES = [Forest, Water, Agriculture, Urban, Others]
EUROSAT_TO_APP = {
    "AnnualCrop": "Agriculture",
    "Forest": "Forest",
    "HerbaceousVegetation": "Agriculture",
    "Highway": "Urban",
    "Industrial": "Urban",
    "Pasture": "Agriculture",
    "PermanentCrop": "Agriculture",
    "Residential": "Urban",
    "River": "Water",
    "SeaLake": "Water",
}

WEIGHTS_PATH = settings.base_dir / "models" / "landcover_cnn.pt"
METRICS_PATH = settings.base_dir / "models" / "landcover_metrics.json"

PATCH = 64          # EuroSAT tile size
STRIDE = 32         # sliding-window stride (overlap smooths the map)
# EuroSAT RGB channel statistics (0-1 scale) used to normalise inputs
_MEAN = [0.3444, 0.3803, 0.4078]
_STD = [0.2037, 0.1366, 0.1148]


def build_model(arch: str = "cnn3"):
    """Model factory shared by training and inference.
    - "cnn3":        3-block CNN + GAP (~0.29M params) — the original baseline.
    - "resnet_lite": compact 4-stage ResNet for 64x64 tiles (~2.8M params, ~155M MACs —
                     about the same compute as cnn3, but 17 conv layers with residuals).
    """
    if not _TORCH:
        raise RuntimeError("PyTorch is not installed")
    if arch == "resnet_lite":
        return _build_resnet_lite()

    class LandCoverCNN(nn.Module):
        def __init__(self, n_classes: int = 10):
            super().__init__()

            def block(cin, cout):
                return nn.Sequential(
                    nn.Conv2d(cin, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(),
                    nn.Conv2d(cout, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(),
                    nn.MaxPool2d(2),
                )

            self.features = nn.Sequential(
                block(3, 32),    # 64 -> 32
                block(32, 64),   # 32 -> 16
                block(64, 128),  # 16 -> 8
            )
            self.head = nn.Sequential(
                nn.AdaptiveAvgPool2d(1), nn.Flatten(),
                nn.Dropout(0.3), nn.Linear(128, n_classes),
            )

        def forward(self, x):
            return self.head(self.features(x))

    return LandCoverCNN()


def _build_resnet_lite(n_classes: int = 10, widths=(32, 64, 128, 256)):
    class Basic(nn.Module):
        def __init__(self, cin, cout, stride):
            super().__init__()
            self.c1 = nn.Conv2d(cin, cout, 3, stride, 1, bias=False)
            self.b1 = nn.BatchNorm2d(cout)
            self.c2 = nn.Conv2d(cout, cout, 3, 1, 1, bias=False)
            self.b2 = nn.BatchNorm2d(cout)
            self.sc = None
            if stride != 1 or cin != cout:
                self.sc = nn.Sequential(nn.Conv2d(cin, cout, 1, stride, bias=False), nn.BatchNorm2d(cout))

        def forward(self, x):
            o = F.relu(self.b1(self.c1(x)))
            o = self.b2(self.c2(o))
            return F.relu(o + (x if self.sc is None else self.sc(x)))

    class ResNetLite(nn.Module):
        def __init__(self):
            super().__init__()
            self.stem = nn.Sequential(nn.Conv2d(3, widths[0], 3, 1, 1, bias=False),
                                      nn.BatchNorm2d(widths[0]), nn.ReLU())
            layers, cin = [], widths[0]
            for cout in widths:                       # every stage halves resolution: 64→32→16→8→4
                layers += [Basic(cin, cout, 2), Basic(cout, cout, 1)]
                cin = cout
            self.layers = nn.Sequential(*layers)
            self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(),
                                      nn.Dropout(0.2), nn.Linear(cin, n_classes))

        def forward(self, x):
            return self.head(self.layers(self.stem(x)))

    return ResNetLite()


# --------------------------------------------------------------------------- #
# Inference
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _load():
    """Load the trained weights once (architecture read from the checkpoint)."""
    if not _TORCH or not WEIGHTS_PATH.exists():
        return None
    ckpt = torch.load(WEIGHTS_PATH, map_location="cpu")
    model = build_model(ckpt.get("arch", "cnn3"))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    model._tta = int(ckpt.get("tta", 1) or 1)          # rotation TTA views used at inference
    torch.set_num_threads(max(1, (torch.get_num_threads() or 4)))
    return model


def available() -> bool:
    return _load() is not None


@lru_cache(maxsize=1)
def metrics() -> dict | None:
    if METRICS_PATH.exists():
        try:
            return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


# EuroSAT-index -> app-class-index projection matrix (10 x 5), built once
@lru_cache(maxsize=1)
def _proj() -> np.ndarray:
    app_idx = {c: i for i, c in enumerate(CLASSES)}
    P = np.zeros((len(EUROSAT_CLASSES), len(CLASSES)), dtype=np.float32)
    for j, ec in enumerate(EUROSAT_CLASSES):
        P[j, app_idx[EUROSAT_TO_APP[ec]]] = 1.0
    return P


def predict_proba(arr: np.ndarray):
    """Slide the CNN over `arr` (H,W,3 uint8) and return full-resolution probability maps:
        p5         (H,W,5)  float -> app-class probabilities (CLASSES order)
        p10        (H,W,10) float -> EuroSAT-class probabilities (EUROSAT_CLASSES order)
        mean_conf  float 0-100    -> mean winning-class probability over the windows
    or None if the model is unavailable. Each pixel averages every window covering it,
    so the map is aligned to the image (no patch-grid offset) and smooth at boundaries.

    Feed the *unenhanced* image: the model was trained on plain EuroSAT RGB, and
    contrast enhancement (CLAHE) drops its in-pipeline accuracy from ~98% to ~78%.
    """
    model = _load()
    if model is None:
        return None
    import cv2

    h0, w0 = arr.shape[:2]
    # Ensure the image is at least one patch in each dimension
    if h0 < PATCH or w0 < PATCH:
        arr = cv2.copyMakeBorder(arr, 0, max(0, PATCH - h0), 0, max(0, PATCH - w0), cv2.BORDER_REFLECT)
    h, w = arr.shape[:2]

    ys = list(range(0, h - PATCH + 1, STRIDE)) or [0]
    xs = list(range(0, w - PATCH + 1, STRIDE)) or [0]
    if ys[-1] != h - PATCH:
        ys.append(h - PATCH)
    if xs[-1] != w - PATCH:
        xs.append(w - PATCH)

    mean = torch.tensor(_MEAN).view(1, 3, 1, 1)
    std = torch.tensor(_STD).view(1, 3, 1, 1)
    acc = np.zeros((h, w, len(EUROSAT_CLASSES)), dtype=np.float32)
    cnt = np.zeros((h, w, 1), dtype=np.float32)
    confs: list[float] = []
    P = _proj()
    k = min(getattr(model, "_tta", 1), 4)

    coords = [(y, x) for y in ys for x in xs]
    for i in range(0, len(coords), 256):
        cc = coords[i:i + 256]
        batch = torch.from_numpy(np.stack([arr[y:y + PATCH, x:x + PATCH, :] for y, x in cc]))
        batch = (batch.permute(0, 3, 1, 2).float() / 255.0 - mean) / std
        with torch.no_grad():
            if k > 1:   # rotation test-time augmentation (overhead imagery has no "up")
                probs = sum(F.softmax(model(torch.rot90(batch, r, dims=(2, 3))), dim=1)
                            for r in range(k)) / k
            else:
                probs = F.softmax(model(batch), dim=1)
        probs = probs.cpu().numpy()                          # (N,10)
        confs.extend((probs @ P).max(axis=1).tolist())
        for (y, x), p in zip(cc, probs):
            acc[y:y + PATCH, x:x + PATCH] += p
            cnt[y:y + PATCH, x:x + PATCH] += 1

    p10 = (acc / np.maximum(cnt, 1))[:h0, :w0]
    return p10 @ P, p10, round(100.0 * float(np.mean(confs)), 1)


def predict_class_map(arr: np.ndarray):
    """CNN-only land-cover map. Returns (class_map (H,W) int in CLASSES space,
    mean_conf 0-100), or None if the model is unavailable."""
    pred = predict_proba(arr)
    if pred is None:
        return None
    p5, _, mean_conf = pred
    return p5.argmax(axis=2).astype(np.int32), mean_conf


def model_summary() -> dict:
    """Compact descriptor for API responses / the PDF report."""
    m = metrics() or {}
    return {
        "type": "EuroSAT-CNN + spectral-texture land-cover segmentation",
        "test_accuracy": m.get("grouped_accuracy_pct", m.get("test_accuracy_pct")),
        "test_accuracy_10class": m.get("test_accuracy_pct"),
        "n_train": m.get("n_train"),
        "n_test": m.get("n_test"),
        "classes": CLASSES,
        "backbone": m.get("backbone", "3-block CNN + GAP"),
        "arch": m.get("arch", "cnn3"),
    }


@lru_cache(maxsize=1)
def pipeline_eval() -> dict | None:
    """Headline numbers from models/segmentation_eval.json (scripts/eval_segmentation.py):
    the full segmentation pipeline scored on EuroSAT held-out tiles and on hand-labelled
    real scenes — the accuracy a user actually gets, not just the CNN's."""
    p = settings.base_dir / "models" / "segmentation_eval.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    e, s = d["eurosat_pipeline"]["pipeline"], d["real_scenes"]["pipeline"]
    return {"eurosat_tiles": d["eurosat_pipeline"]["n_tiles"],
            "eurosat_accuracy_pct": e["grouped_accuracy_pct"],
            "real_scene_probe_accuracy_pct": s["probe_pixel_accuracy_pct"],
            "composition_checks": s["composition_pass"],
            "generated_at": d.get("generated_at")}
