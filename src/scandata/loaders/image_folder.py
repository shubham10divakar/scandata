"""Layout detection and loading for folder datasets (design doc §3.3).

A) class folders        data/<class>/*.jpg
B) split/class folders  data/<train|val|test>/<class>/*.jpg
C) manifest             a CSV with a `path` column (see loaders.manifest)

Nested class hierarchies are flattened to the leaf folder name; the folders in between
are kept as the `domain` (e.g. SDNET2018's D/CD -> label CD, domain D).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd

from scandata.core.index import BASE_COLUMNS, IMAGE_EXTS, DatasetIndex
from scandata.loaders.manifest import SPLIT_NAMES as SPLIT_ALIASES
from scandata.loaders.manifest import find_manifest, load_manifest

SKIP_DIRS = {"__MACOSX"}


class LoaderError(ValueError):
    pass


def _skip_dir(name: str) -> bool:
    # also skip ScanData's own output folders (<report>_assets) if a report lands inside
    return name.startswith(".") or name in SKIP_DIRS or name.endswith("_report_assets")


def _walk(base: Path):
    """Yield (dirpath, subdirs, files) with hidden/tool folders pruned."""
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not _skip_dir(d))
        yield Path(dirpath), dirnames, sorted(filenames)


def apply_group_regex(df: pd.DataFrame, group_regex: str | None) -> bool:
    if not group_regex:
        return False
    pattern = re.compile(group_regex)
    if "group" not in pattern.groupindex:
        raise LoaderError("--group-regex needs a named group: (?P<group>...)")

    def extract(path: str) -> str | None:
        m = pattern.search(Path(path).name)
        return m.group("group") if m else None

    df["group"] = df["path"].map(extract)
    return True


def load(root: str | Path, splits: str = "auto", group_regex: str | None = None) -> DatasetIndex:
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise LoaderError(f"Not a folder: {root}")

    if splits not in ("auto", "none"):
        index = load_manifest(root, Path(splits))
    else:
        top = [d for d in sorted(root.iterdir()) if d.is_dir() and not _skip_dir(d.name)]
        split_dirs = {d: SPLIT_ALIASES[d.name.lower()] for d in top if d.name.lower() in SPLIT_ALIASES}
        manifest = find_manifest(root) if splits == "auto" and not split_dirs else None
        if splits == "auto" and split_dirs:
            index = _load_folders(root, split_dirs)
        elif manifest is not None:
            index = load_manifest(root, manifest)
        else:
            index = _load_folders(root, None)

    index.groups_declared = apply_group_regex(index.df, group_regex) or index.groups_declared
    if index.df.empty:
        raise LoaderError(f"No images found under {root}")
    return index


def _load_folders(root: Path, split_dirs: dict[Path, str] | None) -> DatasetIndex:
    rows: list[dict] = []
    stray: list[tuple[str, str]] = []
    class_counts: dict[str, int] = {}

    bases = list(split_dirs.items()) if split_dirs else [(root, None)]
    if split_dirs:  # anything at the top level that isn't a split folder
        for item in sorted(root.iterdir()):
            if item.is_file() and not item.name.startswith("."):
                stray.append((item.name, "outside the split folders"))
            elif item.is_dir() and item not in split_dirs and not _skip_dir(item.name):
                stray.append((item.name + "/", "folder outside the split folders (ignored)"))

    for base, split in bases:
        for dirpath, subdirs, files in _walk(base):
            rel_dir = dirpath.relative_to(base)
            depth = len(rel_dir.parts)
            images = [f for f in files if Path(f).suffix.lower() in IMAGE_EXTS]
            if depth >= 1 and not subdirs:  # leaf folder = class folder
                class_counts[dirpath.name] = class_counts.get(dirpath.name, 0) + len(images)
            for name in files:
                rel = (dirpath / name).relative_to(root).as_posix()
                if Path(name).suffix.lower() not in IMAGE_EXTS:
                    stray.append((rel, "not an image file"))
                    continue
                if depth == 0:
                    stray.append((rel, "image not inside a class folder"))
                    continue
                rows.append({
                    "path": str(dirpath / name),
                    "relpath": rel,
                    "label": dirpath.name,
                    "split": split,
                    "group": None,
                    "domain": "/".join(rel_dir.parts[:-1]) or None,
                })

    df = pd.DataFrame(rows, columns=BASE_COLUMNS)
    layout = "split-folders" if split_dirs else "class-folders"
    return DatasetIndex(root=root, df=df, layout=layout, stray=stray, class_counts=class_counts)
