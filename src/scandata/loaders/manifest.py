"""Layout C: a CSV manifest with columns path, label[, split][, group]."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scandata.core.index import BASE_COLUMNS, DatasetIndex

SPLIT_NAMES = {
    "train": "train", "training": "train",
    "val": "val", "valid": "val", "validation": "val", "dev": "val",
    "test": "test", "testing": "test",
}


def find_manifest(root: Path) -> Path | None:
    for csv in sorted(root.glob("*.csv")):
        try:
            cols = pd.read_csv(csv, nrows=0).columns.str.lower()
        except (OSError, ValueError):
            continue
        if "path" in cols and "label" in cols:
            return csv
    return None


def load_manifest(root: Path, manifest: Path) -> DatasetIndex:
    from scandata.loaders.image_folder import LoaderError

    manifest = manifest if manifest.is_absolute() else (Path.cwd() / manifest)
    if not manifest.is_file():
        manifest = root / manifest.name
    if not manifest.is_file():
        raise LoaderError(f"Manifest not found: {manifest}")

    raw = pd.read_csv(manifest)
    raw.columns = raw.columns.str.lower().str.strip()
    missing = {"path", "label"} - set(raw.columns)
    if missing:
        raise LoaderError(f"Manifest {manifest.name} is missing columns: {', '.join(sorted(missing))}")

    base = manifest.parent

    def resolve(p: str) -> Path:
        path = Path(str(p))
        return path if path.is_absolute() else base / path

    paths = raw["path"].map(resolve)
    df = pd.DataFrame({
        "path": paths.map(str),
        "relpath": [_rel(p, root) for p in paths],
        "label": raw["label"].astype(str),
        "split": raw["split"].map(lambda s: SPLIT_NAMES.get(str(s).strip().lower(), str(s)))
        if "split" in raw else None,
        "group": raw["group"].astype(str) if "group" in raw else None,
        "domain": raw["domain"].astype(str) if "domain" in raw else None,
    }, columns=BASE_COLUMNS)
    counts = df["label"].value_counts().to_dict()
    return DatasetIndex(
        root=root, df=df, layout="manifest", class_counts=counts,
        groups_declared="group" in raw,
    )


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
