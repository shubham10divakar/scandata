"""Perceptual hashes (64-bit pHash and dHash), implemented with numpy."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image


@lru_cache(maxsize=1)
def _dct_matrix(n: int = 32) -> np.ndarray:
    k = np.arange(n)[:, None]
    i = np.arange(n)[None, :]
    m = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2 / n)
    m[0] /= np.sqrt(2)
    return m


def _bits_to_int(bits: np.ndarray) -> int:
    value = 0
    for b in bits.reshape(-1):
        value = (value << 1) | int(b)
    return value


def phash(gray: Image.Image) -> int:
    arr = np.asarray(gray.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64)
    d = _dct_matrix(32)
    low = (d @ arr @ d.T)[:8, :8]
    return _bits_to_int(low > np.median(low))


def dhash(gray: Image.Image) -> int:
    arr = np.asarray(gray.resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    return _bits_to_int(arr[:, 1:] > arr[:, :-1])


def hashes(rgb: Image.Image) -> dict:
    gray = rgb.convert("L")
    return {"phash": phash(gray), "dhash": dhash(gray)}
