"""Image acquisition & preprocessing.

Mirrors the 'Preprocessing' stage of the methodology: decode, resize, denoise
and enhance, producing a clean RGB uint8 array for the downstream models.
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

from ..config import settings


def load_image(data: bytes) -> np.ndarray:
    """Decode raw bytes into an RGB uint8 numpy array (H, W, 3)."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return np.asarray(img, dtype=np.uint8)


def resize_max(arr: np.ndarray, max_dim: int | None = None) -> np.ndarray:
    """Downscale so the longest side <= max_dim (keeps aspect ratio)."""
    max_dim = max_dim or settings.max_image_dim
    h, w = arr.shape[:2]
    scale = max_dim / float(max(h, w))
    if scale < 1.0:
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        arr = cv2.resize(arr, new_size, interpolation=cv2.INTER_AREA)
    return arr


def enhance(arr: np.ndarray) -> np.ndarray:
    """Denoise (edge-preserving bilateral) + mild contrast enhancement (CLAHE on luminance)."""
    arr = cv2.bilateralFilter(arr, d=5, sigmaColor=45, sigmaSpace=45)
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2RGB)


def preprocess(data: bytes, max_dim: int | None = None) -> np.ndarray:
    """Full preprocessing: decode -> resize -> denoise -> mild contrast enhance."""
    return enhance(resize_max(load_image(data), max_dim))


def preprocess_pair(data: bytes, max_dim: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(enhanced, raw): the enhanced image for display and physical indices, and the same
    decoded + resized image *without* enhancement for the CNN (its training domain)."""
    raw = resize_max(load_image(data), max_dim)
    return enhance(raw), raw


def preprocess_array(arr: np.ndarray, max_dim: int | None = None) -> np.ndarray:
    """Enhance an already-decoded RGB uint8 array (e.g. a multispectral preview)."""
    return enhance(resize_max(arr, max_dim))
