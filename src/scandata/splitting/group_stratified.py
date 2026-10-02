"""Group-aware, stratified, duplicate-safe train/val/test split (about 70/15/15).

Groups are declared source IDs (--group-regex / manifest) merged with near-duplicate
clusters, so every copy of an image and every image of a source lands in one split.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from scandata.analysis.duplicates import DupResult


def build_groups(df: pd.DataFrame, readable: pd.DataFrame, dups: DupResult | None) -> pd.Series:
    groups = pd.Series([f"img{i}" for i in range(len(df))], index=df.index, dtype=object)
    if df["group"].notna().any():
        declared = df["group"].notna()
        groups[declared] = "g:" + df.loc[declared, "group"].astype(str)
    if dups is not None and dups.n_components:
        comp = pd.Series(dups.component, index=readable.index)
        comp = comp[comp >= 0]
        # merge: every row in a duplicate cluster takes the cluster's first group label
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            while parent.get(x, x) != x:
                x = parent[x]
            return x

        for members in comp.groupby(comp).groups.values():
            labels = groups[members].tolist()
            root = find(labels[0])
            for label in labels[1:]:
                r = find(label)
                if r != root:
                    parent[r] = root
        groups = groups.map(find)
    return groups


def suggest_splits(df: pd.DataFrame, groups: pd.Series, seed: int = 42) -> pd.DataFrame | None:
    """None when there are too few independent groups to make three splits."""
    y = df["label"].astype(str).to_numpy()
    g = groups.to_numpy()
    if len(set(g)) < 14:
        return None
    split = np.full(len(df), "train", dtype=object)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # classes smaller than n_splits
        outer = StratifiedGroupKFold(n_splits=7, shuffle=True, random_state=seed)
        rest, test = next(outer.split(np.zeros(len(y)), y, g))
        split[test] = "test"
        inner = StratifiedGroupKFold(n_splits=6, shuffle=True, random_state=seed)
        _, val = next(inner.split(np.zeros(len(rest)), y[rest], g[rest]))
        split[rest[val]] = "val"
    return pd.DataFrame({
        "path": df["relpath"].to_numpy(), "label": y, "split": split,
        "group": [x.removeprefix("g:") for x in g],
    })


def write_suggested_splits(frame: pd.DataFrame, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    return out
