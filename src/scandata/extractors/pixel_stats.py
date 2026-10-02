"""Pixel statistics, thumbnails and border features from one decoded RGB image."""

from __future__ import annotations

import numpy as np
from PIL import Image

MAX_SIDE = 1024  # stats on very large images are computed on a downscaled copy
EDGE_THRESHOLD = 40.0  # gradient magnitude (0-255 scale) that counts as an edge
_GRAY = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def _gray(img: Image.Image) -> np.ndarray:
    return np.asarray(img, dtype=np.float32) @ _GRAY


def edge_density(gray: np.ndarray) -> float:
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    gx = gray[1:-1, 2:] - gray[1:-1, :-2]
    gy = gray[2:, 1:-1] - gray[:-2, 1:-1]
    return float((np.hypot(gx, gy) > EDGE_THRESHOLD).mean())


def laplacian_var(gray: np.ndarray) -> float:
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    lap = (
        gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:]
        - 4 * gray[1:-1, 1:-1]
    )
    return float(lap.var())


def pixel_stats(rgb: Image.Image, target_size: int | None) -> dict:
    if max(rgb.size) > MAX_SIDE:
        rgb = rgb.copy()
        rgb.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.BILINEAR)
    a = np.asarray(rgb, dtype=np.float32)
    gray = a @ _GRAY
    mx, mn = a.max(axis=2), a.min(axis=2)
    saturation = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    hist = np.bincount(np.clip(gray, 0, 255).astype(np.uint8).ravel(), minlength=256)
    p = hist[hist > 0] / hist.sum()
    means = a.mean(axis=(0, 1)) / 255
    stds = a.std(axis=(0, 1)) / 255

    edges = edge_density(gray)
    stats = {
        "mean_r": float(means[0]), "mean_g": float(means[1]), "mean_b": float(means[2]),
        "std_r": float(stds[0]), "std_g": float(stds[1]), "std_b": float(stds[2]),
        "brightness": float(gray.mean()),
        "contrast": float(gray.std()),
        "saturation": float(saturation.mean()),
        "sharpness": laplacian_var(gray),
        "entropy": float(-(p * np.log2(p)).sum()),
        "clipped_frac": float(((gray <= 2) | (gray >= 253)).mean()),
        "edge_density": edges,
        "edge_density_target": None,
    }
    if target_size:
        small = rgb.resize((target_size, target_size), Image.Resampling.BILINEAR)
        stats["edge_density_target"] = edge_density(_gray(small))
    return stats


def thumbnails(rgb: Image.Image) -> dict:
    """8x8 color thumbnail (global color) and the outer 10% frame of a 10x10 grid (background)."""
    thumb = np.asarray(rgb.resize((8, 8), Image.Resampling.BOX), dtype=np.uint8)
    grid = np.asarray(rgb.resize((10, 10), Image.Resampling.BOX), dtype=np.uint8)
    ring = np.ones((10, 10), dtype=bool)
    ring[1:-1, 1:-1] = False
    return {
        "thumb": thumb.reshape(-1).tolist(),
        "border": grid[ring].reshape(-1).tolist(),
    }
