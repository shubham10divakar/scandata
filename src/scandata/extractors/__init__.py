"""Single-pass feature extraction: each image is read and decoded once."""

from __future__ import annotations

import io
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
from PIL import Image

from scandata.core.cache import FeatureCache
from scandata.core.index import DatasetIndex
from scandata.extractors.decode import decode_meta, to_rgb
from scandata.extractors.file_meta import file_meta
from scandata.extractors.hashes import hashes
from scandata.extractors.pixel_stats import pixel_stats, thumbnails

# Bump when any extractor's output changes, so cached features are recomputed.
EXTRACTOR_VERSION = 1
PARALLEL_MIN = 64  # below this many uncached files, process pool startup isn't worth it

Image.MAX_IMAGE_PIXELS = 400_000_000  # allow large scans; still guards against bombs


def extract(path: str, target_size: int | None = None) -> dict:
    rec: dict = {"readable": False, "error": None}
    p = Path(path)
    try:
        data = p.read_bytes()
    except FileNotFoundError:
        rec["error"] = "file not found"
        return rec
    except OSError as exc:
        rec["error"] = f"cannot read file: {exc.strerror or exc}"
        return rec
    rec.update(file_meta(p, data))
    if not data:
        rec["error"] = "zero-byte file"
        return rec
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # Pillow raises many types for corrupt files
        rec["error"] = f"{type(exc).__name__}: {exc}"[:200]
        return rec

    rec.update(decode_meta(img))
    try:
        rgb = to_rgb(img)
        rec.update(pixel_stats(rgb, target_size))
        rec.update(hashes(rgb))
        rec.update(thumbnails(rgb))
    except Exception as exc:
        rec["error"] = f"decoded but could not process pixels: {type(exc).__name__}: {exc}"[:200]
        return rec
    rec["readable"] = True
    return rec


def _extract_star(args: tuple[str, int | None]) -> dict:
    return extract(*args)


def run_extractors(
    index: DatasetIndex,
    target_size: int | None = None,
    use_cache: bool = True,
    workers: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> DatasetIndex:
    """Fill index.df with features for every file. `progress(done, total)` is called as it goes."""
    paths = index.df["path"].tolist()
    total = len(paths)
    records: list[dict | None] = [None] * total

    cache = FeatureCache() if use_cache else None
    keys = [FeatureCache.key(p, EXTRACTOR_VERSION, target_size) for p in paths]
    if cache:
        hits = cache.get_many([k for k in keys if k])
        for i, k in enumerate(keys):
            if k in hits:
                records[i] = hits[k]
    todo = [i for i, r in enumerate(records) if r is None]
    done = total - len(todo)
    if progress:
        progress(done, total)

    fresh: dict[str, dict] = {}
    workers = workers or min(8, os.cpu_count() or 1)
    jobs = [(paths[i], target_size) for i in todo]
    if workers > 1 and len(todo) >= PARALLEL_MIN:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = pool.map(_extract_star, jobs, chunksize=max(1, len(jobs) // (workers * 8)))
            for i, rec in zip(todo, results, strict=True):
                records[i] = rec
                done += 1
                if keys[i] and rec.get("error") != "file not found":
                    fresh[keys[i]] = rec
                if progress:
                    progress(done, total)
    else:
        for i, job in zip(todo, jobs, strict=True):
            rec = _extract_star(job)
            records[i] = rec
            done += 1
            if keys[i]:
                fresh[keys[i]] = rec
            if progress:
                progress(done, total)

    if cache:
        if fresh:
            cache.put_many(fresh)
        cache.close()

    features = pd.DataFrame.from_records(records, index=index.df.index)
    base = index.df.drop(columns=[c for c in features.columns if c in index.df.columns])
    index.df = pd.concat([base, features], axis=1)
    index.df["readable"] = index.df["readable"].fillna(False).astype(bool)
    return index
