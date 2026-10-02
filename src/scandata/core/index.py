"""DatasetIndex: one row per image file, plus what the loader found around them."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
BASE_COLUMNS = ["path", "relpath", "label", "split", "group", "domain"]


@dataclass
class DatasetIndex:
    root: Path
    df: pd.DataFrame
    layout: str  # "class-folders" | "split-folders" | "manifest"
    stray: list[tuple[str, str]] = field(default_factory=list)  # (relpath, reason)
    class_counts: dict[str, int] = field(default_factory=dict)  # every class folder, incl. empty
    groups_declared: bool = False

    @property
    def labels(self) -> list[str]:
        return sorted(self.df["label"].dropna().unique().tolist())

    @property
    def splits(self) -> list[str]:
        order = {"train": 0, "val": 1, "test": 2}
        found = self.df["split"].dropna().unique().tolist()
        return sorted(found, key=lambda s: (order.get(s, 9), s))

    @property
    def has_splits(self) -> bool:
        return len(self.splits) > 1

    @property
    def held_out(self) -> list[str]:
        """Evaluation splits: everything except train."""
        return [s for s in self.splits if s != "train"]

    @property
    def readable(self) -> pd.DataFrame:
        if "readable" not in self.df:
            return self.df
        return self.df[self.df["readable"].fillna(False).astype(bool)]

    def __len__(self) -> int:
        return len(self.df)
