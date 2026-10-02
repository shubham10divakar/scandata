"""File-level metadata: size, extension, real format from magic bytes, sha256."""

from __future__ import annotations

import hashlib
from pathlib import Path

EXT_FORMAT = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".gif": "GIF", ".bmp": "BMP",
    ".tif": "TIFF", ".tiff": "TIFF", ".webp": "WEBP",
}


def magic_format(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if head.startswith(b"BM"):
        return "BMP"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "TIFF"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WEBP"
    return None


def file_meta(path: Path, data: bytes) -> dict:
    ext = path.suffix.lower()
    return {
        "bytes": len(data),
        "ext": ext,
        "ext_format": EXT_FORMAT.get(ext),
        "magic_format": magic_format(data[:16]),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
