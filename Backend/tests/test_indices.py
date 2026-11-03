"""Multispectral index calculation tests."""
import numpy as np


def compute_ndvi(nir, red):
    denom = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where(denom != 0, (nir - red) / denom, 0.0)
    return np.clip(ndvi, -1.0, 1.0)


def test_ndvi_range():
    nir = np.array([0.8, 0.5, 0.1], dtype=np.float32)
    red = np.array([0.1, 0.4, 0.9], dtype=np.float32)
    ndvi = compute_ndvi(nir, red)
    assert np.all(ndvi >= -1.0) and np.all(ndvi <= 1.0)
    assert ndvi[0] > 0.5  # high vegetation
    assert ndvi[2] < 0.0  # low vegetation / water
