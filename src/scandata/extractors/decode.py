"""Decode-level metadata: size, color mode, EXIF, JPEG quality estimate."""

from __future__ import annotations

import numpy as np
from PIL import Image

# Standard JPEG luminance quantization table (quality 50), in zigzag-independent order.
_STD_LUMA = np.array([
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99,
], dtype=np.float64)


def jpeg_quality(img: Image.Image) -> float | None:
    """Estimate libjpeg quality (1-100) from the luminance quantization table."""
    tables = getattr(img, "quantization", None)
    if not tables or 0 not in tables:
        return None
    luma = np.array(tables[0], dtype=np.float64)
    if luma.size != 64:
        return None
    # Pillow returns tables in zigzag order; compare sorted values, which is order-free.
    scale = float(np.mean(np.sort(luma) / np.sort(_STD_LUMA)) * 100)
    quality = (200 - scale) / 2 if scale <= 100 else 5000 / scale
    return round(min(max(quality, 1.0), 100.0), 1)


def decode_meta(img: Image.Image) -> dict:
    exif = img.getexif()
    return {
        "width": img.width,
        "height": img.height,
        "mode": img.mode,
        "format": img.format,
        "n_frames": getattr(img, "n_frames", 1),
        "exif_orientation": exif.get(274),
        "camera_model": str(exif.get(272)).strip("\x00 ") if exif.get(272) else None,
        "jpeg_quality": jpeg_quality(img) if img.format == "JPEG" else None,
    }


def to_rgb(img: Image.Image) -> Image.Image:
    """RGB view for pixel statistics. High-bit-depth images are rescaled to 0-255."""
    if img.mode in ("I", "I;16", "I;16B", "I;16L", "F"):
        arr = np.asarray(img, dtype=np.float64)
        lo, hi = float(arr.min()), float(arr.max())
        arr = (arr - lo) / (hi - lo) * 255 if hi > lo else np.zeros_like(arr)
        return Image.fromarray(arr.astype(np.uint8)).convert("RGB")
    if img.mode == "RGB":
        return img
    return img.convert("RGB")
