"""Thumbnail grids (PNG) referenced from the Markdown report."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

TILE = 128
CAPTION = 16


def _tile(path: str, caption: str) -> Image.Image:
    canvas = Image.new("RGB", (TILE, TILE + CAPTION), "white")
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail((TILE, TILE))
            canvas.paste(img, ((TILE - img.width) // 2, (TILE - img.height) // 2))
    except Exception:
        ImageDraw.Draw(canvas).text((8, TILE // 2), "unreadable", fill="red")
    ImageDraw.Draw(canvas).text((3, TILE + 2), caption[:20], fill="black")
    return canvas


def save_grid(items: list[tuple[str, str]], out: Path, columns: int = 8) -> str | None:
    """items: (image path, caption). Returns the file name written, or None."""
    if not items:
        return None
    rows = (len(items) + columns - 1) // columns
    cols = min(columns, len(items))
    sheet = Image.new("RGB", (cols * TILE, rows * (TILE + CAPTION)), "white")
    for i, (path, caption) in enumerate(items):
        sheet.paste(_tile(path, caption), ((i % cols) * TILE, (i // cols) * (TILE + CAPTION)))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out.name


def save_pairs(pairs: list[tuple[str, str, str, str]], out: Path) -> str | None:
    """pairs: (path_a, caption_a, path_b, caption_b), laid out two pairs per row."""
    items: list[tuple[str, str]] = []
    for a, ca, b, cb in pairs:
        items += [(a, ca), (b, cb)]
    return save_grid(items, out, columns=4)
