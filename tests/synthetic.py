"""Synthetic datasets with known, injected defects (design doc §12)."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def texture(rng: np.random.Generator, size: int = 96) -> Image.Image:
    """A random smooth color texture: distinct pHash per call."""
    small = rng.integers(0, 256, (6, 6, 3), dtype=np.uint8)
    img = Image.fromarray(small).resize((size, size), Image.Resampling.BICUBIC)
    draw = ImageDraw.Draw(img)
    for _ in range(3):
        x0, y0 = rng.integers(0, size - 20, 2)
        w, h = rng.integers(8, 30, 2)
        draw.rectangle([x0, y0, x0 + w, y0 + h], fill=tuple(int(v) for v in rng.integers(0, 256, 3)))
    return img


def crack(img: Image.Image, rng: np.random.Generator) -> Image.Image:
    img = img.copy()
    draw = ImageDraw.Draw(img)
    pts = [(int(rng.integers(0, img.width)), 0)]
    for y in range(8, img.height + 8, 8):
        pts.append((int(np.clip(pts[-1][0] + rng.integers(-6, 7), 0, img.width - 1)), y))
    draw.line(pts, fill=(20, 20, 20), width=2)
    return img


def make_clean(root: Path, per_class: int = 40, seed: int = 0, splits: bool = True,
               classes: tuple[str, ...] = ("cracked", "uncracked")) -> Path:
    """Balanced dataset with no injected defects."""
    rng = np.random.default_rng(seed)
    split_plan = [("train", 0.7), ("val", 0.15), ("test", 0.15)] if splits else [(None, 1.0)]
    for cls in classes:
        n_done = 0
        for split, frac in split_plan:
            n = round(per_class * frac) if split != "test" else per_class - n_done
            folder = root / split / cls if split else root / cls
            folder.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                img = texture(rng)
                if cls == "cracked":
                    img = crack(img, rng)
                img.save(folder / f"{cls[:2]}{n_done + i:04d}.jpg", quality=90)
            n_done += n
    return root


def make_defective(root: Path, seed: int = 1) -> dict[str, list[str]]:
    """Clean split dataset plus one of each defect. Returns what was injected where."""
    make_clean(root, per_class=40, seed=seed)
    rng = np.random.default_rng(seed + 100)
    injected: dict[str, list[str]] = {}

    def add(key: str, path: Path) -> None:
        injected.setdefault(key, []).append(path.relative_to(root).as_posix())

    train_cr = sorted((root / "train" / "cracked").glob("*.jpg"))
    # exact duplicate across splits
    src = train_cr[0]
    dst = root / "test" / "cracked" / "dup_exact.jpg"
    dst.write_bytes(src.read_bytes())
    add("exact_cross", dst)
    # near duplicate across splits (resized + recompressed)
    src = train_cr[1]
    near = root / "test" / "cracked" / "dup_near.jpg"
    Image.open(src).resize((80, 80)).save(near, quality=70)
    add("near_cross", near)
    # label conflict: the same image under the other class
    conflict = root / "train" / "uncracked" / "conflict.jpg"
    conflict.write_bytes(train_cr[2].read_bytes())
    add("label_conflict", conflict)
    # corrupt (truncated) and zero-byte files
    bad = root / "train" / "uncracked" / "truncated.jpg"
    bad.write_bytes(train_cr[3].read_bytes()[:300])
    add("unreadable", bad)
    zero = root / "train" / "cracked" / "empty.jpg"
    zero.write_bytes(b"")
    add("unreadable", zero)
    # PNG saved with a .jpg extension
    buf = io.BytesIO()
    texture(rng).save(buf, format="PNG")
    mismatch = root / "train" / "uncracked" / "really_png.jpg"
    mismatch.write_bytes(buf.getvalue())
    add("format_mismatch", mismatch)
    # blank and tiny images
    blank = root / "val" / "uncracked" / "blank.jpg"
    Image.new("RGB", (96, 96), (0, 0, 0)).save(blank)
    add("blank", blank)
    tiny = root / "val" / "cracked" / "tiny.jpg"
    texture(rng).resize((16, 16)).save(tiny)
    add("tiny", tiny)
    # stray file and EXIF rotation
    (root / "train" / "cracked" / ".DS_Store").write_bytes(b"\0")
    (root / "train" / "cracked" / "notes.txt").write_text("hi")
    add("non_image", root / "train" / "cracked" / "notes.txt")
    rotated = root / "train" / "cracked" / "rotated.jpg"
    img = texture(rng)
    exif = img.getexif()
    exif[274] = 6
    img.save(rotated, exif=exif)
    add("exif_rotation", rotated)
    return injected


def make_shortcut(root: Path, seed: int = 2, per_class: int = 60) -> Path:
    """No splits; class 'a' saved as PNG at 128 px with a white border, class 'b' as JPEG 96 px."""
    rng = np.random.default_rng(seed)
    for cls in ("a", "b"):
        folder = root / cls
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(per_class):
            img = texture(rng)
            if cls == "a":
                framed = Image.new("RGB", (128, 128), (255, 255, 255))
                framed.paste(img, (16, 16))
                framed.save(folder / f"img_{i:03d}.png")
            else:
                img.save(folder / f"img_{i:03d}.jpg", quality=60)
    return root
